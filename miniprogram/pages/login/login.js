var app = getApp();
Page({
  data: {
    loading: false,
    returning: false,
    canLogin: true,
    // Legacy login
    showLegacy: false,
    username: '', password: '',
    legacyLoading: false, legacyError: '',
    // Register
    showRegister: false,
    regUsername: '', regEmail: '', regPhone: '', regPassword: '', regPassword2: '',
    regLoading: false, regError: '',
  },

  onLoad() {
    // Restore token from storage
    const saved = wx.getStorageSync('access_token');
    if (saved) {
      app.globalData.token = saved;
      app.globalData.refreshToken = wx.getStorageSync('refresh_token') || '';
      app.globalData.userInfo = wx.getStorageSync('userInfo');
      // Returning user: auto-skip after brief flash
      this.setData({ returning: true });
      setTimeout(() => {
        wx.switchTab({ url: '/pages/index/index' });
      }, 600);
    }
  },

  // ===== WeChat One-Click Login =====
  async handleWxLogin() {
    if (this.data.loading) return;
    this.setData({ loading: true });

    try {
      // Step 1: Get WeChat login code
      const loginRes = await new Promise((resolve, reject) => {
        wx.login({
          success: resolve,
          fail: reject,
        });
      });

      if (!loginRes.code) {
        throw new Error('获取登录凭证失败');
      }

      // Step 2: Exchange code for JWT (getUserProfile is deprecated, use wx.getUserInfo button approach if needed)
      var res = await app.post('/api/v1/auth/wx-login', {
        code: loginRes.code,
        nickname: '',
        avatar: '',
      }, false);

      // Step 4: Save token and redirect
      app.globalData.token = res.access_token;
      app.globalData.refreshToken = res.refresh_token;
      app.globalData.userInfo = res.user;
      wx.setStorageSync('access_token', res.access_token);
      wx.setStorageSync('refresh_token', res.refresh_token);
      wx.setStorageSync('userInfo', res.user);

      wx.showToast({ title: '登录成功', icon: 'success', duration: 1000 });

      // Redirect: new users → onboarding, others → go back or index
      setTimeout(() => {
        if (res.is_new_user) {
          wx.redirectTo({ url: '/pages/onboarding/onboarding' });
        } else {
          // Try to go back to previous page, fallback to index
          const pages = getCurrentPages();
          if (pages.length > 1) {
            wx.navigateBack();
          } else {
            wx.switchTab({ url: '/pages/index/index' });
          }
        }
      }, 600);

    } catch (e) {
      console.error('WX login error:', e);
      wx.showToast({ title: '登录失败，请重试', icon: 'none' });
    }

    this.setData({ loading: false });
  },

  // ===== Fallback: Phone number auth =====
  async handlePhoneLogin(e) {
    // WeChat phone number quick auth (requires certified mini program)
    const { code } = e.detail;
    if (!code) return;

    this.setData({ loading: true });
    try {
      const res = await app.post('/api/v1/auth/wx-login', { code, phone_code: true }, false);
      app.globalData.token = res.access_token;
      wx.setStorageSync('access_token', res.access_token);
      wx.setStorageSync('userInfo', res.user);
      wx.switchTab({ url: '/pages/index/index' });
    } catch (err) {
      wx.showToast({ title: '登录失败', icon: 'none' });
    }
    this.setData({ loading: false });
  },

  // ===== Legacy Login (hidden by default) =====
  toggleLegacy() { this.setData({ showLegacy: !this.data.showLegacy, showRegister: false }); },
  setUsername(e) { this.setData({ username: e.detail.value }); },
  setPassword(e) { this.setData({ password: e.detail.value }); },

  // Register
  toggleRegister() { this.setData({ showRegister: !this.data.showRegister, showLegacy: false, regError: '' }); },
  setRegUser(e) { this.setData({ regUsername: e.detail.value }); },
  setRegEmail(e) { this.setData({ regEmail: e.detail.value }); },
  setRegPhone(e) { this.setData({ regPhone: e.detail.value }); },
  setRegPwd(e) { this.setData({ regPassword: e.detail.value }); },
  setRegPwd2(e) { this.setData({ regPassword2: e.detail.value }); },

  async handleRegister() {
    if (this.data.regLoading) return;
    var err = '';
    if (!this.data.regUsername || this.data.regUsername.length < 2) err = '用户名至少2个字符';
    else if (!this.data.regEmail || this.data.regEmail.indexOf('@') < 0) err = '请输入有效的邮箱';
    else if (!this.data.regPhone || this.data.regPhone.length < 11) err = '请输入有效的手机号';
    else if (!this.data.regPassword || this.data.regPassword.length < 6) err = '密码至少6个字符';
    else if (this.data.regPassword !== this.data.regPassword2) err = '两次密码不一致';
    if (err) { this.setData({ regError: err }); return; }
    this.setData({ regLoading: true, regError: '' });
    try {
      await app.post('/api/v1/auth/register', {
        username: this.data.regUsername,
        email: this.data.regEmail,
        phone: this.data.regPhone,
        password: this.data.regPassword,
        nickname: this.data.regUsername,
      }, false);
      // Auto login after register
      var res = await app.post('/api/v1/auth/login', {
        username: this.data.regUsername,
        password: this.data.regPassword,
      }, false);
      app.globalData.token = res.access_token;
      app.globalData.refreshToken = res.refresh_token;
      wx.setStorageSync('access_token', res.access_token);
      wx.setStorageSync('refresh_token', res.refresh_token);
      wx.showToast({ title: '注册成功！', icon: 'success' });
      setTimeout(function () { wx.switchTab({ url: '/pages/index/index' }); }, 800);
    } catch (e) {
      this.setData({ regError: (e && e.message) || '注册失败，请重试' });
    }
    this.setData({ regLoading: false });
  },

  async handleLegacyLogin() {
    if (this.data.legacyLoading) return;
    if (!this.data.username || !this.data.password) return;
    this.setData({ legacyLoading: true, legacyError: '' });
    try {
      const res = await app.post('/api/v1/auth/login', {
        username: this.data.username,
        password: this.data.password,
      }, false);
      app.globalData.token = res.access_token;
      app.globalData.refreshToken = res.refresh_token;
      wx.setStorageSync('access_token', res.access_token);
      wx.setStorageSync('refresh_token', res.refresh_token);
      const pages = getCurrentPages();
      if (pages.length > 1) wx.navigateBack();
      else wx.switchTab({ url: '/pages/index/index' });
    } catch (e) {
      this.setData({ legacyError: '用户名或密码错误' });
    }
    this.setData({ legacyLoading: false });
  },
});
