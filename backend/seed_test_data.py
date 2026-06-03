"""Seed test users with realistic sleep data for testing."""
import sys, random, time, json
from datetime import datetime, timedelta, date

sys.path.insert(0, '.')
from app.database import SessionLocal
from app.models import *
from app.services import hash_pw

db = SessionLocal()

def seed():
    print("Seeding test data...")

    # === Create 10 test users ===
    test_users = [
        ("SleepMaster", "s1@test.com", 90, 8.0),
        ("EarlyBird", "s2@test.com", 85, 7.5),
        ("InsomniaFighter", "s3@test.com", 55, 5.5),
        ("ZenBeginner", "s4@test.com", 72, 7.0),
        ("MarathonRunner", "s5@test.com", 88, 8.2),
        ("AnxiousYouth", "s6@test.com", 45, 4.8),
        ("RetiredLife", "s7@test.com", 78, 7.8),
        ("NightOwl", "s8@test.com", 62, 6.0),
        ("NewMom", "s9@test.com", 50, 5.0),
        ("StudentLife", "s10@test.com", 68, 6.5),
    ]

    users = []
    for i, (name, email, base_score, base_dur) in enumerate(test_users):
        u = User(
            username=f"test{i+1}", email=email,
            hashed_password=hash_pw("test123"),
            nickname=name, openid=f"seed_test_{i+1}",
        )
        db.add(u); db.flush()
        users.append((u, base_score, base_dur))

        # Health profile
        goals = ["Fall asleep faster", "Deeper sleep", "Less night waking", "Regular schedule"]
        issues = random.sample(["Hard to fall asleep", "Wake up at night", "Early waking", "Too many dreams", "Light sleep"], 2)
        db.add(HealthProfile(
            user_id=u.id, age=random.randint(18, 65), gender=random.choice(["M", "F"]),
            sleep_goal_hours=random.choice([7, 7.5, 8, 8.5]),
            bedtime_target="22:30", wakeup_target="07:00",
            sleep_issues="、".join(issues),
            stress_level=random.choice(["Low", "Medium", "High"]),
            improvement_priority=",".join(random.sample(goals, 2)),
            caffeine_intake=random.choice(["None", "Occasional", "1-2 cups/day"]),
            exercise_frequency=random.choice(["1-2x/week", "3-5x/week", "Daily"]),
        ))

        # User level
        lv = random.randint(1, 10)
        db.add(UserLevel(user_id=u.id, level=lv, total_xp=lv*100+random.randint(0,50),
                         current_xp=random.randint(0, 99), streak_days=random.randint(0, 14)))

        # Points
        db.add(UserPoints(user_id=u.id, total_points=lv*50+random.randint(0, 30)))

    db.commit()
    print(f"  Created {len(users)} users")

    # === Create 30 days of sleep records ===
    today = date.today()
    total_records = 0
    for u, base_score, base_dur in users:
        for day_offset in range(30, 0, -1):
            d = today - timedelta(days=day_offset)
            if random.random() < 0.15: continue  # Some days missing
            score = max(0, min(100, base_score + random.randint(-15, 15)))
            dur = round(max(3, min(10, base_dur + random.uniform(-1.5, 1.5))), 1)
            bedtime = datetime(d.year, d.month, d.day, random.randint(22, 23), random.randint(0, 59))
            wake_time = bedtime + timedelta(hours=dur)
            tags = random.sample(["深度", "快速入睡", "梦境", "夜醒", "浅睡", "REM"], random.randint(1, 3))
            db.add(SleepRecord(
                user_id=u.id, diary_date=d, bedtime=bedtime, wake_time=wake_time,
                duration_hours=dur, quality=random.randint(1, 5), score=score,
                tags=json.dumps(tags), notes=random.choice(["", "Feeling good today", "Had trouble falling asleep"]),
            ))
            total_records += 1
    db.commit()
    print(f"  Created {total_records} sleep records")

    # === Create community posts ===
    post_contents = [
        "坚持了21天CBT-I课程，睡眠评分从45提升到80！强烈推荐",
        "今晚试试4-7-8呼吸法，真的有帮助吗？",
        "白噪音对我来说太有效了，雨声+篝火组合绝了",
        "最近压力大总是半夜醒来，有什么建议？",
        "分享一个睡眠小技巧：睡前不玩手机+热水泡脚",
        "买了重力毯，第一晚就睡得特别好",
        "冥想App推荐：用了三个月，入睡时间从1小时缩短到15分钟",
        "今天完成了所有每日任务，感觉很充实",
        "有人试过褪黑素吗？效果怎么样？",
        "睡眠花园的第五棵植物终于解锁了！🌳",
        "连续7天满分，精神状态明显好多了",
        "熬夜党求推荐有效助眠方法",
        "分享我的睡眠音乐清单：雨声+钢琴",
        "每天坚持运动真的能改善睡眠",
        "CBT-I第二天课程：刺激控制疗法太实用了",
    ]

    post_ids = []
    for i, (u, _, _) in enumerate(users):
        for _ in range(random.randint(2, 5)):
            content = random.choice(post_contents)
            topic = random.choice(["t1", "t2", "t3", "t4", ""])
            days_ago = random.randint(0, 14)
            created = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
            p = SleepPost(
                user_id=u.id, content=content, topic_id=topic,
                like_count=random.randint(0, 20), comment_count=random.randint(0, 8),
                sleep_score=random.randint(50, 95) if random.random() > 0.3 else None,
                created_at=created,
            )
            db.add(p); db.flush()
            post_ids.append(p.id)
    db.commit()
    print(f"  Created {len(post_ids)} posts")

    # === Add likes to posts ===
    like_count = 0
    for pid in post_ids:
        for u, _, _ in users:
            if random.random() < 0.25:
                db.add(PostLike(post_id=pid, user_id=u.id))
                like_count += 1
    db.commit()
    print(f"  Created {like_count} likes")

    # === Add comments ===
    comment_count = 0
    comment_texts = ["说得好！", "同感", "我也试试", "谢谢分享", "这个方法真的有用", "加油！", "羡慕了"]
    for pid in post_ids[:20]:
        for _ in range(random.randint(1, 4)):
            uid = random.choice(users)[0].id
            db.add(PostComment(post_id=pid, user_id=uid, content=random.choice(comment_texts)))
            comment_count += 1
    db.commit()
    print(f"  Created {comment_count} comments")

    # === Create follow relationships ===
    follow_count = 0
    for u1, _, _ in users:
        for u2, _, _ in users:
            if u1.id != u2.id and random.random() < 0.3:
                db.add(UserFollow(follower_id=u1.id, followee_id=u2.id))
                follow_count += 1
    db.commit()
    print(f"  Created {follow_count} follows")

    # === Create task completions ===
    task_count = 0
    for u, _, _ in users:
        for day_offset in range(7, 0, -1):
            date_key = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            for tid in random.sample(["t1","t2","t3","t4","t5","t6","t7","t8"], random.randint(1, 6)):
                db.add(TaskCompletion(user_id=u.id, task_id=tid, date_key=date_key, points=5))
                task_count += 1
    db.commit()
    print(f"  Created {task_count} task completions")

    # === Create notifications ===
    notif_count = 0
    for u, _, _ in users:
        for _ in range(random.randint(0, 5)):
            db.add(Notification(
                user_id=u.id, type=random.choice(["like", "comment", "follow"]),
                title=random.choice(["新点赞", "新评论", "新粉丝"]),
                body=f"有人{random.choice(['赞了你的帖子', '评论了你的帖子', '关注了你'])}",
                related_id=random.choice(post_ids or [1]),
                is_read=random.choice([0, 1]),
            ))
            notif_count += 1
    db.commit()
    print(f"  Created {notif_count} notifications")

    # === Create game progress ===
    game_date = today.strftime("%Y-%m-%d")
    game_count = 0
    for u, _, _ in users:
        for gid in ["g_v_br", "g_v_qz"]:
            if not db.query(TaskCompletion).filter(TaskCompletion.user_id == u.id, TaskCompletion.task_id == gid, TaskCompletion.date_key == game_date).first():
                db.add(TaskCompletion(user_id=u.id, task_id=gid, date_key=game_date, points=5))
                game_count += 1
    db.commit()
    print(f"  Created {game_count} game visits")

    # === Create badge unlocks ===
    badge_count = 0
    badge_ids = ["b1", "b2", "b3", "b4", "b5"]
    for u, _, _ in users:
        for bid in random.sample(badge_ids, random.randint(1, 4)):
            if not db.query(BadgeUnlock).filter(BadgeUnlock.user_id == u.id, BadgeUnlock.badge_id == bid).first():
                db.add(BadgeUnlock(user_id=u.id, badge_id=bid))
                badge_count += 1
    db.commit()
    print(f"  Created {badge_count} badge unlocks")

    # === Create program progress (21-day course) ===
    prog_count = 0
    for u, _, _ in users:
        if random.random() > 0.3:
            day = random.randint(1, 21)
            db.add(ProgramProgress(user_id=u.id, current_day=day, completed=1 if day >= 21 else 0))
            prog_count += 1
    db.commit()
    print(f"  Created {prog_count} program enrollments")

    # Done
    print(f"\nSeed complete! Test credentials: test1~test10 / password: test123")
    print(f"Try: http://127.0.0.1:8000/")

if __name__ == "__main__":
    seed()
