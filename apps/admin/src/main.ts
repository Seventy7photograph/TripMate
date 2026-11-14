// 文件说明：管理后台模块：main。
import "@fontsource/dm-serif-display/latin-400.css";
import "@fontsource/manrope/latin-400.css";
import "@fontsource/manrope/latin-500.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "element-plus/theme-chalk/base.css";
import "element-plus/theme-chalk/el-card.css";
import "element-plus/theme-chalk/el-container.css";
import "element-plus/theme-chalk/el-header.css";
import "element-plus/theme-chalk/el-main.css";
import "element-plus/theme-chalk/el-tag.css";

import {
  ElCard,
  ElContainer,
  ElHeader,
  ElMain,
  ElTag,
} from "element-plus";
import { createApp } from "vue";

import App from "./App.vue";
import "./styles.css";

const app = createApp(App);
app.component("ElCard", ElCard);
app.component("ElContainer", ElContainer);
app.component("ElHeader", ElHeader);
app.component("ElMain", ElMain);
app.component("ElTag", ElTag);
app.mount("#app");

