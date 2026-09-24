import type {ReactNode} from 'react'
import './globals.css'
export const metadata={title:'OSTutorLLM · AI Operating Systems Lab',description:'A local-first Operating Systems learning and simulation platform'}
export default function RootLayout({children}:{children:ReactNode}){return <html lang="en"><body>{children}</body></html>}
