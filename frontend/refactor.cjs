// 历史布局重构脚本：通过字符串替换快速调整旧版 App 布局结构。
const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src/App.tsx');
let content = fs.readFileSync(filePath, 'utf8');

// We need to extract the sections
const myWorkRegex = /\{\/\* Left Column: My Work & Todos \*\/\}\s*<section className="xl:col-span-2 bg-white\/40 backdrop-blur-xl border border-white\/60 rounded-3xl p-6 shadow-\[0_8px_30px_rgb\(0,0,0,0\.02\)\] flex flex-col">([\s\S]*?)<\/section>/;
const aiAssistantRegex = /\{\/\* Right: AI Hero Search Section \*\/\}\s*<section className="xl:col-span-1 flex flex-col">([\s\S]*?)<\/section>/;
const commonFunctionsRegex = /\{\/\* Left: Common Functions \(Systems\) \*\/\}\s*<section className="xl:col-span-2 bg-white\/40 backdrop-blur-xl border border-white\/60 rounded-3xl p-6 shadow-\[0_8px_30px_rgb\(0,0,0,0\.02\)\] flex flex-col">([\s\S]*?)<\/section>/;
const statsRegex = /\{\/\* Section: AI Stats \*\/\}\s*<section className="bg-white\/40 backdrop-blur-xl border border-white\/60 rounded-3xl p-6 shadow-\[0_8px_30px_rgb\(0,0,0,0\.02\)\]">([\s\S]*?)<\/section>/;
const noticesRegex = /\{\/\* Section: Notices \*\/\}\s*<section className="bg-white\/40 backdrop-blur-xl border border-white\/60 rounded-3xl p-6 shadow-\[0_8px_30px_rgb\(0,0,0,0\.02\)\] flex flex-col">([\s\S]*?)<\/section>/;

const myWorkMatch = content.match(myWorkRegex);
const aiAssistantMatch = content.match(aiAssistantRegex);
const commonFunctionsMatch = content.match(commonFunctionsRegex);
const statsMatch = content.match(statsRegex);
const noticesMatch = content.match(noticesRegex);

if (!myWorkMatch || !aiAssistantMatch || !commonFunctionsMatch || !statsMatch || !noticesMatch) {
  console.error("Could not find all sections");
  process.exit(1);
}

const myWorkInner = myWorkMatch[1];
const aiAssistantInner = aiAssistantMatch[1];
const commonFunctionsInner = commonFunctionsMatch[1];
const statsInner = statsMatch[1];
let noticesInner = noticesMatch[1];

// Modify noticesInner to use grid if it's col-span-2
noticesInner = noticesInner.replace('className="space-y-5 flex-1"', 'className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1"');
noticesInner = noticesInner.replace(/className={\`group pb-5 \${idx !== NOTICES\.length - 1 \? 'border-b border-slate-100' : ''}\`}/g, 'className="group"');

const newLayout = `
            {/* Top Section: My Work & Todos */}
            <div className="mb-6">
              <section className="bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
${myWorkInner}
              </section>
            </div>

            {/* Middle Section: AI Assistant & Common Functions */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
              {/* Left: AI Hero Search Section */}
              <section className="xl:col-span-1 flex flex-col">
${aiAssistantInner}
              </section>

              {/* Right: Common Functions (Systems) */}
              <section className="xl:col-span-2 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
${commonFunctionsInner}
              </section>
            </div>

            {/* Bottom Section: Stats & Notices */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Left: AI Stats */}
              <section className="xl:col-span-1 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
${statsInner}
              </section>

              {/* Right: Notices */}
              <section className="xl:col-span-2 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
${noticesInner}
              </section>
            </div>
`;

const startMarker = `{/* Top Section: My Work & Todos and AI Hero Search */}`;
const startIndex = content.indexOf(startMarker);
const endMarker = `              </div>\n            </div>`;
const endMarkerIndex = content.indexOf(endMarker, content.indexOf(`{/* Bottom Section: Common Functions & Stats/Notices */}`));

if (startIndex === -1 || endMarkerIndex === -1) {
  console.error("Markers not found");
  process.exit(1);
}

const contentBefore = content.substring(0, startIndex);
const contentAfter = content.substring(endMarkerIndex + endMarker.length);

fs.writeFileSync(filePath, contentBefore + newLayout.trim() + '\n' + contentAfter, 'utf8');
console.log("Refactored successfully");
