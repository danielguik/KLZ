import {Config} from '@remotion/cli/config';
import fs from 'fs';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// Na nuvem usamos o Chromium já instalado; na sua máquina o Remotion baixa o dele.
const chromium = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
if (fs.existsSync(chromium)) Config.setBrowserExecutable(chromium);
