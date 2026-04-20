import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "element-plus/es/components/message/style/css";
// 显式引入服务式确认框样式，避免 ElMessageBox 在按需构建后出现未样式化弹层。
import "element-plus/es/components/message-box/style/css";
import "./styles/theme.css";
import "./styles/base.css";

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount("#app");
