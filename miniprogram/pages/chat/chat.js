const app = getApp();

Page({
  data: {
    messages: [],
    sessions: [],
    activeSession: null,
    inputMsg: '',
    sending: false,
    quickQuestions: ['如何改善失眠问题？', '什么是最佳睡眠时间？', '睡前应该做什么？', '分析一下我的睡眠数据'],
  },

  onShow() { this.loadSessions(); },

  async loadSessions() {
    try { this.setData({ sessions: await app.get('/api/v1/chat/sessions') }); } catch {}
  },

  async openSession(e) {
    const id = e.currentTarget.dataset.id;
    try { const data = await app.get(`/api/v1/chat/sessions/${id}`); this.setData({ activeSession: id, messages: data.messages || [] }); } catch {}
  },

  newChat() { this.setData({ activeSession: null, messages: [] }); },

  async sendMessage() {
    const text = this.data.inputMsg.trim();
    if (!text || this.data.sending) return;
    this.setData({ sending: true, inputMsg: '' });
    this.data.messages.push({ id: Date.now(), role: 'user', content: text });
    // 正在输入中占位气泡
    const typingId = 'typing_' + Date.now();
    this.data.messages.push({ id: typingId, role: 'assistant', content: '正在思考...', isTyping: true });

    try {
      const data = await app.post('/api/v1/chat/send', { session_id: this.data.activeSession, message: text });
      // 移除占位气泡
      const typingIdx = this.data.messages.findIndex(m => m.isTyping);
      if (typingIdx >= 0) this.data.messages.splice(typingIdx, 1);
      this.data.messages.push({ id: data.id, role: data.role, content: data.content });
      if (!this.data.activeSession) { this.setData({ activeSession: data.session_id }); this.loadSessions(); }
    } catch {
      const typingIdx = this.data.messages.findIndex(m => m.isTyping);
      if (typingIdx >= 0) this.data.messages.splice(typingIdx, 1);
      this.data.messages.push({ id: Date.now() + 1, role: 'assistant', content: '抱歉，暂时无法回复。' });
    }
    this.setData({ messages: [...this.data.messages], sending: false });
  },

  sendQuick(e) { this.setData({ inputMsg: e.currentTarget.dataset.q }); this.sendMessage(); },
  onInput(e) { this.setData({ inputMsg: e.detail.value }); },
});
