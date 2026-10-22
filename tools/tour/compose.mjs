// Cuts the filmed tour to plan.json and lays it out as a 1080×1920 video: a caption above the
// phone for each scene, touch rings where the screen answered, and the landing page's end card.
// Silent; mix.py adds the narration. Needs ffmpeg, Chrome and Python with Pillow.
// Usage: node compose.mjs <recording dir> <out.mp4>
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const [REC, OUT] = process.argv.slice(2);
const REPO = fileURLToPath(new URL('../../', import.meta.url));
const ASSETS = join(REC, 'assets');
mkdirSync(ASSETS, { recursive: true });
mkdirSync(dirname(OUT), { recursive: true });
execFileSync('python3', [new URL('bezel.py', import.meta.url).pathname, ASSETS, join(REPO, 'ios/WhoWasWhen/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png')], { stdio: 'inherit' });

const plan = JSON.parse(readFileSync(join(REC, 'plan.json'), 'utf8'));
const CARD = 5; // seconds the end card holds
const total = plan.end + CARD;
const SCREEN = { x: 198, y: 350, w: 684, h: 1488 }; // screen.mp4, from retime.py
const SCALE = SCREEN.w / 402; // the film is 402 points wide

// The landing page's look: white with a soft indigo glow, ink text, indigo and gold accents, and
// the system font throughout, bold and tight for headings. System fonts only, as on the page.
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
const html = (body) => `<!doctype html><html><head><meta charset="utf-8"><style>
  html, body { margin: 0; width: 1080px; height: 1920px; color: #161823;
    background: radial-gradient(1400px 700px at 85% -10%, #eef0ff, transparent 60%), linear-gradient(180deg, #ffffff, #f7f8fc);
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif; }
  .cap { position: absolute; top: 80px; left: 90px; right: 90px; }
  .cap h1 { font-size: 70px; line-height: 1.05; font-weight: 700; letter-spacing: -0.02em; margin: 0; }
  .cap p { font-size: 34px; line-height: 1.3; margin: 16px 0 0; color: #5b6072; }
  .end { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; }
  .end img { width: 280px; height: 280px; border-radius: 62px; box-shadow: 0 10px 30px rgba(31,40,80,.18); }
  .end h2 { font-size: 110px; line-height: 1.1; font-weight: 700; letter-spacing: -0.02em; margin: 60px 0 0; }
  .end h2 span { color: #4338ca; }
  .end .tag { font-size: 44px; line-height: 1.3; color: #5b6072; margin: 24px 130px 0; }
  .end .get { font-size: 36px; font-weight: 600; color: #161823; margin-top: 60px; line-height: 1.5; }
</style></head><body>${body}</body></html>`;
const shoot = async (body, file) => {
  await page.setContent(html(body), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: join(ASSETS, file) });
};
for (const [i, c] of plan.captions.entries()) await shoot(`<div class="cap"><h1>${c.title}</h1><p>${c.sub}</p></div>`, `caption-${i}.png`);
const icon = readFileSync(join(ASSETS, 'icon.png')).toString('base64');
await shoot(
  `<div class="end"><img src="data:image/png;base64,${icon}"><h2>Who<span>Was</span>When</h2>
   <div class="tag">Travel through history on your phone</div>
   <div class="get">Free on the App Store and Google Play</div></div>`,
  'end.png',
);
await browser.close();

// Background: each caption until the next, then the end card.
const bg = [];
plan.captions.forEach((c, i) => {
  const to = plan.captions[i + 1]?.t ?? plan.end;
  bg.push(`file 'caption-${i}.png'`, `duration ${(to - (i === 0 ? 0 : c.t)).toFixed(3)}`);
});
bg.push(`file 'end.png'`, `duration ${CARD.toFixed(3)}`, `file 'end.png'`);
writeFileSync(join(ASSETS, 'bg.txt'), bg.join('\n') + '\n');

// The screen, cut to the kept pieces and joined.
const n = plan.keep.length;
const filters = [`[1:v]split=${n}${plan.keep.map((_, i) => `[p${i}]`).join('')}`];
plan.keep.forEach(([s, e], i) => filters.push(`[p${i}]trim=start=${s}:end=${e},setpts=PTS-STARTPTS[k${i}]`));
filters.push(`${plan.keep.map((_, i) => `[k${i}]`).join('')}concat=n=${n}:v=1:a=0[app]`);
filters.push(`[0:v]fps=30,format=yuv420p[bg]`);
filters.push(`[bg][app]overlay=${SCREEN.x}:${SCREEN.y}:enable='lt(t,${plan.end})'[v0]`);
filters.push(`[v0][2:v]overlay=0:0:enable='lt(t,${plan.end})'[v1]`);
let last = 'v1';
plan.touches.forEach((tp, i) => {
  const x = SCREEN.x + tp.x * SCALE - 45;
  const y = Math.round(SCREEN.y + tp.y * SCALE - 45);
  // A swipe's ring travels with the finger; a tap's stays put.
  const dur = tp.type === 'swipe' ? 0.5 : 0.5;
  const xExpr = tp.type === 'swipe' ? `'${x.toFixed(0)}+(t-${tp.t})/${dur}*${(tp.dx * SCALE).toFixed(0)}'` : x.toFixed(0);
  filters.push(`[${last}][3:v]overlay=x=${xExpr}:y=${y}:enable='between(t,${tp.t},${(tp.t + dur).toFixed(3)})'[t${i}]`);
  last = `t${i}`;
});
filters.push(`[${last}]fade=t=in:st=0:d=0.4,fade=t=out:st=${(total - 0.6).toFixed(2)}:d=0.6[out]`);

execFileSync('ffmpeg', [
  '-y', '-loglevel', 'error',
  '-f', 'concat', '-safe', '0', '-i', join(ASSETS, 'bg.txt'),
  '-i', join(REC, 'screen.mp4'),
  '-loop', '1', '-i', join(ASSETS, 'bezel.png'),
  '-loop', '1', '-i', join(ASSETS, 'tap.png'),
  '-filter_complex', filters.join(';'),
  '-map', '[out]', '-t', total.toFixed(2),
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
  OUT,
], { stdio: 'inherit' });
console.log('wrote', OUT, `${total.toFixed(1)}s`);
