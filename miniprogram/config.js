/**
 * 梦眠阁小程序 — 环境配置
 *
 * API 域名切换规则:
 *   wx.getAccountInfoSync().envVersion === 'release' → PROD_HOST
 *   否则 (develop / trial)                        → DEV_HOST
 *
 * 生产域名必须在微信后台「开发管理 > 服务器域名」配置为 request 合法域名。
 */

const DEV_HOST = 'http://127.0.0.1:8000';       // 本地开发
const PROD_HOST = 'https://api.your-domain.com'; // TODO: 上线前替换为实际域名

function resolveApiBase() {
  try {
    var accountInfo = wx.getAccountInfoSync();
    if (accountInfo.miniProgram.envVersion === 'release') {
      return PROD_HOST;
    }
  } catch (_) { /* 低版本基础库不支持，用 DEV_HOST */ }
  return DEV_HOST;
}

module.exports = {
  DEV_HOST: DEV_HOST,
  PROD_HOST: PROD_HOST,
  apiBase: resolveApiBase(),
};
