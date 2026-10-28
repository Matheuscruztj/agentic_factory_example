from eval_engine.experiments import PromptArm, Trial, compare_prompts
from eval_engine.schema import EvalCase


def test_paired_experiment_recommends_review_but_never_promotes():
    cases = [
        EvalCase("a", "backend", "dev", "pass", ("tests",), critical=True),
        EvalCase("b", "backend", "dev", "pass", ("tests",)),
    ]

    def evaluator(arm, case, seed, max_tokens):
        candidate = arm.name == "candidate"
        return Trial(
            case.id,
            "pass" if candidate or case.id == "a" else "reject",
            False,
            True,
            100 + seed,
            10,
            max_tokens // 2,
            0.01,
        )

    report = compare_prompts(
        baseline=PromptArm("baseline", "Use concise instructions."),
        candidate=PromptArm("candidate", "List requirements, evidence, and checks."),
        cases=cases,
        evaluator=evaluator,
        seed=17,
        max_tokens=100,
        minimum_pass_rate_delta=0.4,
    )

    assert report["promotion_eligible"]
    assert report["auto_promoted"] is False
    assert report["promotion_decision"] == "human_review_required"
    assert report["baseline"]["cost_per_accepted_task_usd"] == 0.01


def test_critical_regression_blocks_candidate():
    cases = [EvalCase("security", "security", "regression", "pass", ("policy",), critical=True)]
    report = compare_prompts(
        baseline=PromptArm("baseline", "safe"),
        candidate=PromptArm("candidate", "unsafe"),
        cases=cases,
        evaluator=lambda arm, case, seed, budget: Trial(
            case.id, "pass" if arm.name == "baseline" else "reject", False, True, 10, 1, 1, 0.0
        ),
        seed=1,
        max_tokens=8,
    )
    assert not report["promotion_eligible"]
    assert report["comparison"]["critical_regressions"] == ["security"]
