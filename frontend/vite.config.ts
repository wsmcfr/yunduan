import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      imports: ["vue", "vue-router", "pinia"],
      resolvers: [
        ElementPlusResolver({
          importStyle: "css",
        }),
      ],
      dts: "auto-imports.d.ts",
    }),
    Components({
      resolvers: [
        ElementPlusResolver({
          importStyle: "css",
          directives: true,
        }),
      ],
      dts: "components.d.ts",
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        /**
         * 将核心框架拆成独立 chunk。
         * Element Plus 已走按需引入，这里不再强行打成整包，
         * 否则会抵消按需加载的收益。
         */
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
        },
      },
    },
  },
});
