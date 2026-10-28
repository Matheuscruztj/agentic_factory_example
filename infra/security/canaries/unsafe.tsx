export function unsafe(value: string) {
  eval(value)
  new Function(value)
  return <div dangerouslySetInnerHTML={{ __html: value }} />
}
