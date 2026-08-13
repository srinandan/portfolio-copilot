import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { initTracing } from './services/tracing';
import './style.css';

// Start distributed tracing (span export + flush lifecycle). Trace context is
// propagated onto every API/SSE request by the ApiService (see services/api.ts).
initTracing();

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
