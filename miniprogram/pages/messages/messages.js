const app = getApp();
Page({
  data: {
    conversations: [], loading: true,
    // Chat view
    chatUser: null, chatMessages: [], chatInput: '', sending: false,
    sendImage: '',
    recording: false, recordTime: 0, recordTimer: null,
  },
  onShow() { this.loadConversations(); },
  async loadConversations() {
    this.setData({ loading: true });
    try {
      const d = await app.get('/api/v1/community/messages/conversations');
      this.setData({ conversations: d.conversations || [], loading: false });
    } catch { this.setData({ loading: false }); }
  },
  async openChat(e) {
    const userId = e.currentTarget.dataset.userId;
    const nickname = e.currentTarget.dataset.nickname;
    this.setData({ chatUser: { id: userId, nickname: nickname }, chatMessages: [], chatInput: '' });
    try {
      const d = await app.get('/api/v1/community/messages/' + userId);
      this.setData({ chatMessages: d.messages || [] });
      this.scrollToBottom();
    } catch {}
  },
  closeChat() {
    this.setData({ chatUser: null, chatMessages: [] });
    this.loadConversations();
  },
  onChatInput(e) { this.setData({ chatInput: e.detail.value }); },
  async sendMessage() {
    if ((!this.data.chatInput.trim() && !this.data.sendImage) || !this.data.chatUser || this.data.sending) return;
    this.setData({ sending: true });
    const body = { content: this.data.chatInput };
    if (this.data.sendImage) body.image_url = this.data.sendImage;
    try {
      const res = await app.post('/api/v1/community/messages/' + this.data.chatUser.id, body);
      const msg = {
        id: res.id, content: this.data.chatInput,
        image_url: this.data.sendImage,
        sender_id: app.globalData.userInfo?.id || 0,
        created_at: new Date().toISOString(),
      };
      this.setData({
        chatMessages: [...this.data.chatMessages, msg],
        chatInput: '', sendImage: '', sending: false,
      });
      this.scrollToBottom();
    } catch { this.setData({ sending: false }); wx.showToast({ title: '发送失败', icon: 'none' }); }
  },
  chooseChatImage() {
    wx.chooseImage({
      count: 1, sizeType: ['compressed'],
      success: (res) => {
        wx.getFileSystemManager().readFile({
          filePath: res.tempFilePaths[0], encoding: 'base64',
          success: async (fileRes) => {
            try {
              const d = await app.post('/api/v1/community/upload', { image: fileRes.data });
              this.setData({ sendImage: d.url || '' });
            } catch {}
          },
        });
      },
    });
  },
  removeChatImage() { this.setData({ sendImage: '' }); },
  scrollToBottom() {
    setTimeout(() => {
      wx.createSelectorQuery().select('#chatBottom').boundingClientRect(() => {
        wx.pageScrollTo({ scrollTop: 99999, duration: 200 });
      }).exec();
    }, 100);
  },
  // Voice recording
  startRecord() {
    this.setData({ recording: true, recordTime: 0 });
    const timer = setInterval(() => {
      this.setData({ recordTime: this.data.recordTime + 1 });
    }, 1000);
    this.setData({ recordTimer: timer });
    const recorder = wx.getRecorderManager();
    recorder.start({ format: 'mp3', duration: 60000 });
    this._recorder = recorder;
    recorder.onStop((res) => {
      clearInterval(this.data.recordTimer);
      this.setData({ recording: false });
      if (res.duration < 1000) return; // too short
      // Read as base64
      wx.getFileSystemManager().readFile({
        filePath: res.tempFilePath, encoding: 'base64',
        success: async (fileRes) => {
          try {
            const d = await app.post('/api/v1/community/upload-voice', {
              voice: fileRes.data,
              duration: Math.round(res.duration / 1000),
            });
            await app.post('/api/v1/community/messages/' + this.data.chatUser.id, {
              content: '[语音]',
              voice_url: d.url,
              voice_duration: d.duration,
            });
            this.setData({
              chatMessages: [...this.data.chatMessages, {
                id: Date.now(), content: '[语音 ' + d.duration + 's]',
                voice_url: d.url, voice_duration: d.duration,
                sender_id: app.globalData.userInfo?.id || 0,
                created_at: new Date().toISOString(),
              }],
            });
            this.scrollToBottom();
          } catch {}
        },
      });
    });
  },
  stopRecord() {
    if (this._recorder) this._recorder.stop();
    if (this.data.recordTimer) clearInterval(this.data.recordTimer);
  },
  playVoice(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    const audio = wx.createInnerAudioContext();
    audio.src = (app.globalData.apiBase || '') + url;
    audio.play();
  },
});
