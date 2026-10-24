/// <reference types="vite/client" />
import React from 'react'
import { createRoot } from 'react-dom/client'
import { Dashboard } from './features/dashboard/Dashboard'
import './styles.css'
createRoot(document.getElementById('root')!).render(<React.StrictMode><Dashboard /></React.StrictMode>)
