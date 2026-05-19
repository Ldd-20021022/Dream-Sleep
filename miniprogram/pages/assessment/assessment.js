const app = getApp();
Page({
  data: { scales: [], selected: null, questions: [], answers: {}, result: null, loading: false, answeredCount: 0, totalCount: 0 },
  onShow() { app.get('/api/v1/wellness/assessments').then(d => this.setData({ scales: d.scales || [] })).catch(() => {}); },
  selectScale(e) {
    var id = e.currentTarget.dataset.id;
    this.setData({ selected: id, answers: {}, result: null, answeredCount: 0 });
    var that = this;
    app.get('/api/v1/wellness/assessments/' + id).then(function (d) {
      var qs = d.questions || [];
      that.setData({ questions: qs, totalCount: qs.length });
    }).catch(function () {});
  },
  setAnswer(e) {
    var qid = String(e.currentTarget.dataset.qid);
    var val = parseInt(e.currentTarget.dataset.val);
    var answers = {};
    var keys = Object.keys(this.data.answers);
    for (var i = 0; i < keys.length; i++) { answers[keys[i]] = this.data.answers[keys[i]]; }
    answers[qid] = val;
    var count = Object.keys(answers).length;
    this.setData({ answers: answers, answeredCount: count });
  },
  async submit() {
    this.setData({ loading: true });
    try { const data = await app.post('/api/v1/wellness/assessments/' + this.data.selected + '/submit', { answers: this.data.answers }); this.setData({ result: data }); } catch {}
    this.setData({ loading: false });
  },
  goBack() { this.setData({ selected: null, questions: [], answers: {}, result: null }); },
});
