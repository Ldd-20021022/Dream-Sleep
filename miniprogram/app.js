/**
 * 梦眠 - 梦境守护者 微信小程序
 */
const DEV_HOST = 'http://192.168.3.64:8000';
const PROD_HOST = 'https://your-domain.com';
const USE_PROD = false;

App({
  globalData: {
    apiBase: USE_PROD ? PROD_HOST : DEV_HOST,
    token: '',
    refreshToken: '',
    userInfo: null,
    // Guardian state
    guardian: { focus: 0, wisdom: 0, resilience: 0, vitality: 0, fragments: [], scenes: ['default'], garden: { plants: 0, flowers: 0, trees: 0, watered: false, streak: 0 }, postcards: [], discoveries: [], ritualStreak: 0, lastRitual: '', lastLogin: '' },
    // Goal tips
    goalTips: {
      '入睡速度': ['今晚试试4-7-8呼吸法，帮大脑快速切换到睡眠模式', '睡前1小时放下手机，蓝光会推迟你的入睡时间', '泡个热水澡能帮你快速降温入睡', '今天试试渐进式肌肉放松法：从脚趾到额头逐一收紧再放松'],
      '睡眠深度': ['今天增加30分钟有氧运动，深睡时长可能增加20%', '保持卧室凉爽(18-22°C)能让深睡阶段更稳定', '镁元素帮助神经系统放松，多吃菠菜、杏仁', '今天减少咖啡因摄入，它在体内停留长达6小时'],
      '减少夜醒': ['睡前2小时不要大量饮水，减少夜起次数', '检查卧室是否有微光或噪音干扰', '酒精会让你半夜醒来——今晚试试不喝酒', '压力是夜醒的头号原因，试试写下来'],
      '作息规律': ['设一个固定闹钟，即使是周末也同一时间起床', '今天试着比昨天早睡15分钟，小步子更容易坚持', '固定起床时间比固定入睡时间更重要', '午睡不要超过30分钟，下午2点后小睡会影响晚上'],
      '减少做梦': ['睡前避免恐怖电影或刺激内容', '写日记把烦心事倒出来，减少夜间思维反刍', '保持卧室通风——氧气不足会导致睡眠不安', '睡前一小时听白噪音，屏蔽环境干扰'],
      '精力恢复': ['白天晒15分钟太阳，帮助校准生物钟', '今天记录午后的精力状态', '晚餐不要吃太饱，消化负担会影响睡眠修复效率', '睡前一小时远离电子屏幕，让你的大脑真正休息']
    },
    surpriseEvents: ['梦鲸跃出海面，溅起一片星辉', '一只夜莺停在花园，唱了一首歌', '梦境边界出现了一扇发光的门', '天空飘下彩色的雪花，落在手心是温热的', '一座倒悬的塔从云层中缓缓降下', '整个梦境世界变成了秋天的金黄色', '远处传来鲸歌，低沉而悠长', '一群发光的蝴蝶从花园飞过', '月亮变成了你守护者的模样', '海面上浮现出银河的倒影'],
    priList: [] // user's improvement priorities
  },

  onLaunch() {
    const token = wx.getStorageSync('access_token');
    if (token) {
      this.globalData.token = token;
      this.globalData.refreshToken = wx.getStorageSync('refresh_token') || '';
    }
    // Load guardian state
    const g = wx.getStorageSync('guardian');
    if (g) this.globalData.guardian = g;
    // Load priorities
    const pri = wx.getStorageSync('priList');
    if (pri) this.globalData.priList = pri;
  },

  // --- Guardian helpers ---
  saveGuardian() { wx.setStorageSync('guardian', this.globalData.guardian); },
  addAttr(attr, amt) {
    const g = this.globalData.guardian;
    g[attr] = Math.min(4, (g[attr] || 0) + amt);
    this.saveGuardian();
    if (g[attr] >= 4) {
      const names = { focus: '专注力', wisdom: '智慧', resilience: '韧性', vitality: '活力' };
      wx.showToast({ title: '🌟 ' + names[attr] + ' 已满级！', icon: 'none' });
    }
  },
  addFragment(quality) {
    const names = ['梦境尘埃', '星河碎片', '极光之晶', '龙鳞', '凤凰羽毛', '月光石', '深海珍珠', '彩虹棱镜'];
    const qNames = { common: '普通', rare: '稀有', epic: '史诗', legendary: '传奇' };
    const f = { id: Date.now(), name: names[Math.floor(Math.random() * names.length)], quality: quality || 'common', date: this._today() };
    this.globalData.guardian.fragments.push(f);
    this.saveGuardian();
    wx.showToast({ title: '✨ 获得 ' + qNames[f.quality] + ' · ' + f.name, icon: 'none' });
  },
  addPostcard(scene, score) {
    this.globalData.guardian.postcards.unshift({ id: Date.now(), scene: scene || '神秘梦境', date: this._today(), score: score || 0 });
    if (this.globalData.guardian.postcards.length > 50) this.globalData.guardian.postcards.length = 50;
    this.saveGuardian();
  },
  addDiscovery(text) {
    this.globalData.guardian.discoveries.unshift({ id: Date.now(), text: text, date: this._today() });
    if (this.globalData.guardian.discoveries.length > 20) this.globalData.guardian.discoveries.length = 20;
    this.saveGuardian();
  },
  waterGarden() {
    const g = this.globalData.guardian.garden;
    if (g.watered) return;
    g.watered = true;
    g.streak++;
    g.plants = Math.max(g.plants, g.streak);
    if (g.streak % 7 === 0) { g.flowers++; wx.showToast({ title: '🌸 一朵新花绽放了！', icon: 'none' }); }
    if (g.streak % 30 === 0) { g.trees++; wx.showToast({ title: '🌳 一棵梦境之树长成了！', icon: 'none' }); }
    this.saveGuardian();
  },
  dailyReset() {
    const today = this._today();
    const g = this.globalData.guardian;
    if (g.lastLogin !== today) {
      // Check garden wilt
      if (g.garden.watered) {
        const lastDate = g.lastRitual || g.lastLogin;
        if (lastDate) {
          const days = Math.floor((Date.now() - new Date(lastDate).getTime()) / 86400000);
          if (days >= 3 && g.garden.flowers > 0) {
            g.garden.flowers--;
            g.garden.streak = Math.max(0, g.garden.streak - 3);
            wx.showToast({ title: '🥀 一朵花因缺水凋零了...今晚记录睡眠可以救活它', icon: 'none' });
          }
        }
      }
      g.garden.watered = false;
      g.lastLogin = today;
      this.saveGuardian();
    }
  },
  getDailyTip() {
    const goals = this.globalData.priList.length > 0 ? this.globalData.priList : ['入睡速度'];
    const allTips = [];
    goals.forEach(function (g) {
      var tips = this.globalData.goalTips[g];
      if (tips) allTips.push.apply(allTips, tips);
    }.bind(this));
    if (allTips.length === 0) return '保持固定的起床时间，即使是周末也尽量不赖床。';
    return allTips[new Date().getDate() % allTips.length];
  },
  rollSurprise() {
    if (Math.random() < 0.2) {
      var events = this.globalData.surpriseEvents;
      return events[Math.floor(Math.random() * events.length)];
    }
    return '';
  },
  getDreamScene(score) {
    if (!score && score !== 0) return { icon: '🌙', title: '梦境海 · 等待记录', sub: '记录昨晚的睡眠，开启你的梦境世界', bg: 'linear-gradient(135deg, #1a1520, #201825)' };
    if (score >= 85) return { icon: '🌟', title: '梦境海 · 晴朗星空', sub: '你的梦境世界今天格外明亮', bg: 'linear-gradient(135deg, #0a1628, #0d2137)' };
    if (score >= 70) return { icon: '🌤️', title: '梦境海 · 微风多云', sub: '守护者在安静地巡视着这片海域', bg: 'linear-gradient(135deg, #1a1a2e, #16213e)' };
    if (score >= 50) return { icon: '☁️', title: '梦境海 · 薄雾笼罩', sub: '迷雾中隐约能看到花园的轮廓', bg: 'linear-gradient(135deg, #1e1e30, #252540)' };
    return { icon: '🌧️', title: '梦境海 · 需要守护', sub: '今晚做一次睡前仪式可以驱散迷雾', bg: 'linear-gradient(135deg, #1a1520, #201825)' };
  },
  _today() { var d = new Date(); return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); },

  // --- HTTP ---
  request(method, path, data, needAuth) {
    needAuth = needAuth !== false;
    var that = this;
    return new Promise(function (resolve, reject) {
      var header = { 'Content-Type': 'application/json' };
      if (needAuth && that.globalData.token) {
        header['Authorization'] = 'Bearer ' + that.globalData.token;
      }
      if (needAuth && !that.globalData.token) {
        that._promptLogin();
        reject(new Error('AUTH_REQUIRED'));
        return;
      }
      wx.request({
        url: that.globalData.apiBase + path,
        method: method,
        data: method === 'GET' ? undefined : data,
        header: header,
        success: function (res) {
          if (res.statusCode === 401) {
            if (that.globalData.refreshToken) {
              that.refreshToken().then(function () {
                that.request(method, path, data, needAuth).then(resolve).catch(reject);
              }).catch(function () {
                that.logout();
                that._promptLogin();
                reject(new Error('AUTH_REQUIRED'));
              });
            } else {
              that._promptLogin();
              reject(new Error('AUTH_REQUIRED'));
            }
            return;
          }
          if (res.statusCode >= 400) {
            reject(new Error(res.data && res.data.detail ? res.data.detail : '请求失败(' + res.statusCode + ')'));
            return;
          }
          resolve(res.data);
        },
        fail: function (err) {
          reject(new Error('网络错误'));
        },
      });
    });
  },

  _loginShownThisSession: false,
  _promptLogin() {
    if (this._loginShownThisSession) return;
    this._loginShownThisSession = true;
    wx.showModal({
      title: '需要登录',
      content: '登录后即可使用全部功能',
      confirmText: '去登录',
      cancelText: '稍后再说',
      success: function (res) {
        if (res.confirm) {
          wx.navigateTo({ url: '/pages/login/login' });
        }
      },
    });
  },

  get(path, needAuth) { return this.request('GET', path, {}, needAuth); },
  post(path, data, needAuth) { return this.request('POST', path, data, needAuth); },
  put(path, data, needAuth) { return this.request('PUT', path, data, needAuth); },
  del(path, data, needAuth) { return this.request('DELETE', path, data, needAuth); },

  async refreshToken() {
    var res = await this.post('/api/v1/auth/refresh', { refresh_token: this.globalData.refreshToken }, false);
    this.globalData.token = res.access_token;
    wx.setStorageSync('access_token', res.access_token);
    return res;
  },

  async checkLogin() {
    try {
      var user = await this.get('/api/v1/auth/me');
      this.globalData.userInfo = user;
      wx.setStorageSync('userInfo', user);
    } catch (e) {
      this.logout();
    }
  },

  async login(username, password) {
    var res = await this.post('/api/v1/auth/login', { username: username, password: password }, false);
    this.globalData.token = res.access_token;
    this.globalData.refreshToken = res.refresh_token;
    wx.setStorageSync('access_token', res.access_token);
    wx.setStorageSync('refresh_token', res.refresh_token);
    await this.checkLogin();
    return this.globalData.userInfo;
  },

  logout() {
    this.globalData.token = '';
    this.globalData.refreshToken = '';
    this.globalData.userInfo = null;
    wx.removeStorageSync('access_token');
    wx.removeStorageSync('refresh_token');
    wx.removeStorageSync('userInfo');
  },
});
