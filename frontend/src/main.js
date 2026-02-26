import { mount } from 'svelte'
import App from './App.svelte'

// Local fonts for GDPR compliance
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'

import './app.css'
const app = mount(App, { target: document.getElementById('app') })

export default app
