import auth from './auth.json';
import billing from './billing.json';
import cacheAnalytics from './cacheAnalytics.json';
import channels from './channels.json';
import common from './common.json';
import dashboard from './dashboard.json';
import logs from './logs.json';
import management from './management.json';
import mcp from './mcp.json';
import models from './models.json';
import playground from './playground.json';
import pool from './pool.json';
import realtime from './realtime.json';
import settings from './settings.json';
import tools from './tools.json';

const translations = {
  ...common,
  ...auth,
  ...dashboard,
  ...settings,
  ...management,
  ...playground,
  ...realtime,
  ...models,
  ...billing,
  ...cacheAnalytics,
  ...logs,
  ...mcp,
  ...tools,
  ...pool,
  channels: {
    ...(management.channels || {}),
    ...channels,
  },
};

export default translations;
