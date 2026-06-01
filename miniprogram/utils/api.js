/** API path constants — mirrors FastAPI backend routes */
const API = {
  AUTH: {
    WX_LOGIN: '/api/v1/auth/wx-login',
    REGISTER: '/api/v1/auth/register',
    LOGIN: '/api/v1/auth/login',
    REFRESH: '/api/v1/auth/refresh',
    ME: '/api/v1/auth/me',
    HAS_PROFILE: '/api/v1/auth/has-profile',
  },
  SLEEP: {
    LIST: '/api/v1/sleep-records',
    LAST: '/api/v1/sleep-records/last',
    STATS: '/api/v1/sleep-records/stats/summary',
    ENHANCED: '/api/v1/sleep-records/stats/enhanced',
    REPORT: '/api/v1/sleep-records/report',
    EXPORT: '/api/v1/sleep-records/export',
  },
  PROFILE: '/api/v1/profiles',
  CHAT: {
    SESSIONS: '/api/v1/chat/sessions',
    SEND: '/api/v1/chat/send',
  },
  TASKS: {
    TODAY: '/api/v1/tasks/today',
    COMPLETE: '/api/v1/tasks/complete',
    UNCOMPLETE: '/api/v1/tasks/complete',  // DELETE method, same path as COMPLETE
    POINTS: '/api/v1/tasks/points/summary',
    BADGES: '/api/v1/tasks/badges',
  },
  WELLNESS: {
    KNOWLEDGE_ARTICLES: '/api/v1/wellness/knowledge/articles',
    PLANS: '/api/v1/wellness/plans',
    ACTIVE_PLAN: '/api/v1/wellness/plans/active',
    ENROLL: '/api/v1/wellness/plans',
    CHECKIN: '/api/v1/wellness/plans/checkin',
    RECOMMEND: '/api/v1/wellness/recommend-plan',
    ONBOARDING: '/api/v1/wellness/onboarding',
  },
};
module.exports = API;
