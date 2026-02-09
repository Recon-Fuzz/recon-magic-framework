import 'tsconfig-paths/register'
import yargs from 'yargs/yargs';
import { hideBin } from 'yargs/helpers'
import runner from './runner';

import * as Sentry from "@sentry/node";

Sentry.init({
  dsn: "https://15f6a91447a41b46589a2293b16d993a@o4506744902254592.ingest.sentry.io/4506745058295808",

});

const argv = yargs(hideBin(process.argv)).argv as any

runner(argv)