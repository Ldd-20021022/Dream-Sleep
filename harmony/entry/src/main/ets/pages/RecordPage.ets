// 梦眠阁 — 睡眠记录 (计时器模式 + 快捷感受)
import { Colors, Spacing, Radius } from '../common/Constants';
import { ApiService } from '../common/ApiService';

@Component
export struct RecordPage {
  @State timerState: string = 'idle'; // idle | sleeping | woke
  @State elapsed: string = '00:00:00';
  @State quickFeel: string = 'ok';
  @State quickStatus: string = 'fast_sleep';
  private api: ApiService = new ApiService();

  build() {
    Scroll() {
      Column() {
        // Mode switch
        Row() {
          Button('⏱ 计时器').fontSize(13).backgroundColor(Colors.PRIMARY).borderRadius(8).layoutWeight(1)
          Button('📝 手动填').fontSize(13).backgroundColor('transparent').fontColor(Colors.TX2).borderRadius(8).layoutWeight(1)
        }
        .padding(4).borderRadius(10).backgroundColor(Colors.CARD)
        .margin({ bottom: 14 })

        if (this.timerState === 'idle') { this.IdleState() }
        else if (this.timerState === 'sleeping') { this.SleepingState() }
        else { this.WokeState() }
      }
      .padding(Spacing.LG)
    }
    .backgroundColor(Colors.BG)
  }

  @Builder IdleState() {
    Column() {
      Text('🌙').fontSize(56)
      Text('点击下方按钮开始记录睡眠').fontSize(14).fontColor(Colors.TX3).margin({ top: 12, bottom: 24 })
      Button('💤 开始睡眠')
        .fontSize(16).backgroundColor(Colors.PRIMARY).borderRadius(Radius.FULL)
        .width('100%').padding(14)
        .onClick(() => { this.timerState = 'sleeping'; })
    }
    .justifyContent(FlexAlign.Center)
    .height(300)
  }

  @Builder SleepingState() {
    Column() {
      Text('😴').fontSize(56)
      Text('正在睡眠中...').fontSize(14).fontColor(Colors.TX3).margin({ top: 8 })
      Text(this.elapsed).fontSize(36).fontWeight(700).margin({ top: 12, bottom: 20 })
      Button('☀️ 我醒了')
        .fontSize(16).backgroundColor(Colors.PRIMARY).borderRadius(Radius.FULL)
        .width('100%').padding(14)
        .onClick(() => { this.timerState = 'woke'; })
      Button('取消').fontSize(13).backgroundColor('transparent').fontColor(Colors.TX3).margin({ top: 8 })
        .onClick(() => { this.timerState = 'idle'; })
    }
    .justifyContent(FlexAlign.Center)
    .height(300)
  }

  @Builder WokeState() {
    Column() {
      Text('☀️').fontSize(44)
      Text('早上好！').fontSize(18).fontWeight(700).fontColor(Colors.TX)
      Text('睡眠时长：7:32:15').fontSize(14).fontColor(Colors.TX2).margin({ top: 4, bottom: 20 })

      // Quick Feel
      Column() {
        Text('感觉怎么样？').fontSize(14).fontWeight(600).fontColor(Colors.TX).margin({ bottom: 10 })
        Row() {
          this.FeelBtn('⚡ 精力充沛', 'great')
          this.FeelBtn('👍 还行', 'ok')
        }
        Row() {
          this.FeelBtn('😴 有点困', 'tired')
          this.FeelBtn('😫 很疲惫', 'bad')
        }
      }
      .padding(16).borderRadius(Radius.XL).backgroundColor(Colors.CARD)

      // Quick Status
      Column() {
        Text('昨晚状态？').fontSize(14).fontWeight(600).fontColor(Colors.TX).margin({ top: 16, bottom: 10 })
        Row() {
          this.StatusBtn('💨 倒头就睡', 'fast_sleep')
          this.StatusBtn('🔄 翻来覆去', 'toss')
        }
        Row() {
          this.StatusBtn('🌙 半夜醒了', 'wake_up')
          this.StatusBtn('💭 做梦了', 'dream')
        }
      }
      .padding(16).borderRadius(Radius.XL).backgroundColor(Colors.CARD)

      Button('✅ 提交记录')
        .fontSize(14).backgroundColor(Colors.PRIMARY).borderRadius(Radius.FULL)
        .width('100%').padding(14).margin({ top: 16 })
        .onClick(() => { this.timerState = 'idle'; })
    }
  }

  @Builder FeelBtn(label: string, feel: string) {
    Button(label)
      .fontSize(12)
      .backgroundColor(this.quickFeel === feel ? Colors.PRIMARY_SOFT : 'transparent')
      .fontColor(this.quickFeel === feel ? Colors.PRIMARY : Colors.TX2)
      .border({ width: 1, color: this.quickFeel === feel ? Colors.PRIMARY : Colors.BORDER })
      .borderRadius(18).padding({ top: 8, bottom: 8, left: 12, right: 12 })
      .layoutWeight(1).margin(4)
      .onClick(() => { this.quickFeel = feel; })
  }

  @Builder StatusBtn(label: string, status: string) {
    Button(label)
      .fontSize(12)
      .backgroundColor(this.quickStatus === status ? Colors.PRIMARY_SOFT : 'transparent')
      .fontColor(this.quickStatus === status ? Colors.PRIMARY : Colors.TX2)
      .border({ width: 1, color: this.quickStatus === status ? Colors.PRIMARY : Colors.BORDER })
      .borderRadius(18).padding({ top: 8, bottom: 8, left: 12, right: 12 })
      .layoutWeight(1).margin(4)
      .onClick(() => { this.quickStatus = status; })
  }
}
