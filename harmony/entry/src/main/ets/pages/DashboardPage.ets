// 梦眠阁 — 首页仪表盘 (v3 MVP: 5区块)
import { Colors, Spacing, Radius, FontSize } from '../common/Constants';
import { ApiService } from '../common/ApiService';

@Component
export struct DashboardPage {
  @State dashboard: object | null = null;
  @State loading: boolean = true;
  private api: ApiService = new ApiService();

  aboutToAppear() { this.loadData(); }

  async loadData() {
    try {
      const d = await this.api.get('/api/v1/wellness/dashboard');
      this.dashboard = d;
    } catch (e) {}
    this.loading = false;
  }

  build() {
    if (this.loading) {
      return Column() { LoadingProgress().color(Colors.PRIMARY) }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
    }

    Scroll() {
      Column() {
        // 1. Dream Scene
        this.DreamScene()
        // 2. Stats Grid
        this.StatsGrid()
        // 3. Streak
        this.StreakMotivation()
        // 4. Quick Actions
        this.QuickActions()
        // 5. Daily Tip
        this.DailyTip()
      }
      .padding(Spacing.LG)
    }
    .backgroundColor(Colors.BG)
  }

  @Builder DreamScene() {
    Column() {
      Text('🌟').fontSize(48)
      Text('梦境海 · 晴朗星空').fontSize(18).fontWeight(600).fontColor(Colors.TX).margin({ top: 8 })
      Text('守护者在安静地巡视着这片海域').fontSize(12).fontColor(Colors.TX3).margin({ top: 4 })
      Row() {
        Button('📝 记录睡眠').fontSize(13).backgroundColor(Colors.PRIMARY).borderRadius(Radius.FULL)
        Button('🎵 白噪音').fontSize(13).backgroundColor('rgba(255,255,255,0.08)').borderRadius(Radius.FULL)
      }
      .margin({ top: 16 })
      .justifyContent(FlexAlign.Center)
    }
    .padding(24).borderRadius(Radius.XL)
    .linearGradient({ direction: GradientDirection.Top, colors: [['#0a1628', 0], ['#0d2137', 1]] })
  }

  @Builder StatsGrid() {
    Grid() {
      GridItem() { this.StatCard('昨晚睡眠', '7.5h') }
      GridItem() { this.StatCard('睡眠评分', '82', Colors.TEAL, '优秀') }
      GridItem() { this.StatCard('连续达标', '🔥🔥 7天', Colors.WARN) }
      GridItem() { this.StatCard('守护者', 'Lv.5', Colors.PRIMARY, '梦境旅人') }
    }
    .columnsTemplate('1fr 1fr')
    .rowsGap(10).columnsGap(10)
    .margin({ top: 12 })
  }

  @Builder StatCard(label: string, value: string, valColor?: string, sub?: string) {
    Column() {
      Text(label).fontSize(10).fontColor(Colors.TX3)
      Text(value).fontSize(24).fontWeight(700).fontColor(valColor || Colors.TX).margin({ top: 4 })
      if (sub) { Text(sub).fontSize(10).fontColor(Colors.TX3).margin({ top: 2 }) }
    }
    .padding(14).borderRadius(Radius.LG)
    .backgroundColor(Colors.CARD)
    .justifyContent(FlexAlign.Center)
  }

  @Builder StreakMotivation() {
    Row() {
      Text('🔥🔥 连续 7 天达标！已解锁「规律达人」徽章 🌟')
        .fontSize(13).fontColor(Colors.TEAL).textAlign(TextAlign.Center)
    }
    .width('100%').padding(14).borderRadius(Radius.LG)
    .backgroundColor(Colors.TEAL_SOFT)
    .margin({ top: 12 })
  }

  @Builder QuickActions() {
    Grid() {
      GridItem() { this.QaItem('📝', '记录') }
      GridItem() { this.QaItem('🎯', '任务') }
      GridItem() { this.QaItem('🤖', 'AI教练') }
      GridItem() { this.QaItem('🎵', '白噪音') }
    }
    .columnsTemplate('1fr 1fr 1fr 1fr')
    .rowsGap(8).columnsGap(8)
    .padding(16).borderRadius(Radius.XL)
    .backgroundColor(Colors.CARD)
    .margin({ top: 12 })
  }

  @Builder QaItem(icon: string, label: string) {
    Column() {
      Text(icon).fontSize(22)
      Text(label).fontSize(10).fontColor(Colors.TX2).margin({ top: 6 })
    }
    .padding({ top: 12, bottom: 12 })
    .justifyContent(FlexAlign.Center)
  }

  @Builder DailyTip() {
    Row() {
      Text('💡').fontSize(22)
      Text('今晚试试4-7-8呼吸法：吸气4秒、屏息7秒、呼气8秒')
        .fontSize(12).fontColor(Colors.TX2).layoutWeight(1).margin({ left: 10 })
    }
    .padding(16).borderRadius(Radius.LG)
    .linearGradient({ direction: GradientDirection.Right, colors: [[Colors.PRIMARY_SOFT, 0], [Colors.TEAL_SOFT, 1]] })
    .margin({ top: 12 })
  }
}
