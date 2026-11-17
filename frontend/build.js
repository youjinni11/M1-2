// Vercel 빌드 스크립트 (외부 패키지 없음)
// 정적 파일을 dist/로 복사하고, 환경 변수 API_BASE_URL로 config.js를 만든다.
const fs = require("fs");
const path = require("path");

const out = path.join(__dirname, "dist");
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out);

for (const file of ["index.html", "styles.css", "app.js"]) {
  fs.copyFileSync(path.join(__dirname, file), path.join(out, file));
}

const apiBaseUrl = process.env.API_BASE_URL;
if (!apiBaseUrl) {
  console.warn("⚠️  API_BASE_URL 환경 변수가 없습니다. 로컬 기본값(http://127.0.0.1:8000)을 사용합니다.");
}
fs.writeFileSync(
  path.join(out, "config.js"),
  `window.APP_CONFIG = ${JSON.stringify({ API_BASE_URL: apiBaseUrl || "http://127.0.0.1:8000" })};\n`
);
console.log("✅ build 완료 → dist/ (API_BASE_URL =", apiBaseUrl || "(기본값)", ")");
