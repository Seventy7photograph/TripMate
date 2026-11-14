// 文件说明：Vite 构建配置。
import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [vue()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": {
          target:
            process.env.VITE_API_PROXY_TARGET ||
            env.VITE_API_PROXY_TARGET ||
            "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 4173,
      strictPort: true,
      proxy: {
        "/api": {
          target:
            process.env.VITE_API_PROXY_TARGET ||
            env.VITE_API_PROXY_TARGET ||
            "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
