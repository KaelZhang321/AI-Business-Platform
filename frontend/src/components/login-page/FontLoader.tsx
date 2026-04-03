// 登录页字体加载器：
// 这里使用内联 style + @import，确保该页面独立渲染时也能拿到 Inter 字体，
// 不依赖全局样式入口的字体声明。
export function FontLoader() {
  return (
    <style
      dangerouslySetInnerHTML={{
        __html: `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  `,
      }}
    />
  );
}
