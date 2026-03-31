// 导出工具：支持将当前工作台导出为 HTML 或图片文件。
import { toPng } from 'html-to-image';

export const exportToHtml = (elementId: string, fileName: string = 'export.html') => {
  const element = document.getElementById(elementId);
  if (!element) {
    console.error(`Element with id ${elementId} not found`);
    return;
  }

  // 导出 HTML 时把当前工作台容器内容包一层完整文档，便于离线查看。
  const htmlContent = `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>${fileName}</title>
      <script src="https://cdn.tailwindcss.com"></script>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        body { 
          font-family: 'Inter', sans-serif; 
          background-color: #F4F6F8; 
          margin: 0;
          padding: 0;
          height: 100vh;
          overflow: hidden;
        }
        .export-container {
          display: flex;
          height: 100vh;
          width: 100vw;
          overflow: hidden;
        }
      </style>
    </head>
    <body>
      <div class="export-container">
        ${element.innerHTML}
      </div>
    </body>
    </html>
  `;

  const blob = new Blob([htmlContent], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

export const exportToImage = async (elementId: string, fileName: string = 'export.png') => {
  const element = document.getElementById(elementId);
  if (!element) {
    console.error(`Element with id ${elementId} not found`);
    return;
  }

  try {
    // 通过 html-to-image 生成 PNG，适合工作台截图式导出。
    const dataUrl = await toPng(element, {
      backgroundColor: '#F4F6F8',
      style: {
        borderRadius: '0',
      },
    });
    const link = document.createElement('a');
    link.download = fileName;
    link.href = dataUrl;
    link.click();
  } catch (error) {
    console.error('Error exporting image:', error);
  }
};
