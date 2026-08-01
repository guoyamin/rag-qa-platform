/// <reference types="vite/client" />

// element-plus 的 locale .mjs 文件缺少类型声明
declare module 'element-plus/dist/locale/zh-cn.mjs' {
  const locale: any
  export default locale
}
