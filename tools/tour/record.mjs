// Films the app tour: builds WhoWasWhen, installs it fresh on the simulator (so Favorites and
// quiz scores start empty), then records the screen while runner/TourTests drives it. Writes
// film.mp4 as recorded, screen.mp4 retimed to a steady 30 fps (see retime.py), and events.json
// (times from the film's first frame). Portraits and summaries come from Wikipedia, so it needs
// a connection. Usage: node record.mjs <simulator udid> <out dir>
import { execFileSync, spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const [SIM, OUT] = process.argv.slice(2);
if (!SIM || !OUT) throw new Error('Usage: node record.mjs <simulator udid> <out dir>');
const HERE = fileURLToPath(new URL('.', import.meta.url));
const REPO = fileURLToPath(new URL('../../', import.meta.url));
const BUNDLE = 'com.giovannicoppola.WhoWasWhen';
const run = (cmd, args, opts = {}) => execFileSync(cmd, args, { stdio: ['ignore', 'ignore', 'inherit'], ...opts });
mkdirSync(OUT, { recursive: true });

// The app, from its generated project (ios/DEVELOPMENT.md).
const derived = join(OUT, 'derived');
run('xcodegen', ['generate', '--spec', `${REPO}ios/project.yml`, '--project', `${REPO}ios`]);
run('xcodebuild', ['-project', `${REPO}ios/WhoWasWhen.xcodeproj`, '-scheme', 'WhoWasWhen', '-configuration', 'Release',
  '-destination', `id=${SIM}`, '-derivedDataPath', derived, 'build', 'CODE_SIGNING_ALLOWED=NO']);
run('xcrun', ['simctl', 'bootstatus', SIM, '-b']);
run('xcrun', ['simctl', 'uninstall', SIM, BUNDLE]);
run('xcrun', ['simctl', 'install', SIM, join(derived, 'Build/Products/Release-iphonesimulator/WhoWasWhen.app')]);
// The landing page is light, and a pinned status bar keeps the film from dating itself.
run('xcrun', ['simctl', 'ui', SIM, 'appearance', 'light']);
run('xcrun', ['simctl', 'status_bar', SIM, 'override', '--time', '9:41', '--batteryState', 'charged', '--batteryLevel', '100', '--wifiBars', '3', '--cellularBars', '4']);

// The tour runner, built before filming so the film doesn't open on compiling.
const runner = ['-project', join(HERE, 'runner/WhoWasWhenTour.xcodeproj'), '-scheme', 'TourTests', '-destination', `id=${SIM}`, '-derivedDataPath', join(OUT, 'runner')];
run('xcodegen', ['generate', '--spec', join(HERE, 'runner/project.yml'), '--project', join(HERE, 'runner')]);
run('xcodebuild', ['build-for-testing', ...runner]);

const film = join(OUT, 'film.mp4');
const recorder = spawn('xcrun', ['simctl', 'io', SIM, 'recordVideo', '--codec=h264', '--force', film]);
const t0 = await new Promise((resolve, reject) => {
  recorder.stderr.on('data', (d) => String(d).includes('Recording started') && resolve(Date.now() / 1000));
  recorder.on('exit', (code) => reject(new Error(`recordVideo exited ${code}`)));
});

const events = [];
const test = spawn('xcodebuild', ['test-without-building', ...runner]);
let buffer = '';
test.stdout.on('data', (d) => {
  buffer += d;
  const lines = buffer.split('\n');
  buffer = lines.pop();
  for (const line of lines) {
    const at = line.indexOf('TOUR ');
    if (at >= 0) events.push(JSON.parse(line.slice(at + 5)));
    if (/error:|failed|Test Case .* passed/.test(line)) console.log(line.trim());
  }
});
const code = await new Promise((resolve) => test.on('exit', resolve));
recorder.kill('SIGINT');
await new Promise((resolve) => recorder.on('exit', resolve));
run('xcrun', ['simctl', 'status_bar', SIM, 'clear']);
writeFileSync(join(OUT, 'events.json'), JSON.stringify(events.map((e) => ({ ...e, t: e.t - t0 })), null, 1));
if (code !== 0) throw new Error(`the tour failed (xcodebuild exited ${code}); events.json shows how far it got`);

execFileSync('python3', [join(HERE, 'retime.py'), OUT], { stdio: 'inherit' });
console.log(`${events.length} events, film in ${film}`);
