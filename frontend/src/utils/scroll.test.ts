import { describe, expect, it } from "vitest";
import {
  distanceFromBottom,
  isNearBottom,
  JUMP_HIDE_THRESHOLD,
  JUMP_SHOW_THRESHOLD,
  PIN_THRESHOLD,
  resolveJumpButtonVisible,
  resolvePinState,
} from "./scroll";

describe("isNearBottom", () => {
  it("恰好滚到底部时贴底", () => {
    // 文档 2000，视口 800，滚动 1200 → 距底 0
    expect(isNearBottom({ scrollHeight: 2000, scrollY: 1200, viewportHeight: 800 })).toBe(true);
  });

  it("距底部在阈值内时贴底", () => {
    // 距底 100 < 120
    expect(isNearBottom({ scrollHeight: 2000, scrollY: 1100, viewportHeight: 800 })).toBe(true);
  });

  it("恰好等于阈值时仍算贴底（边界包含）", () => {
    expect(
      isNearBottom({ scrollHeight: 2000, scrollY: 2000 - 800 - PIN_THRESHOLD, viewportHeight: 800 })
    ).toBe(true);
  });

  it("超出阈值一像素即不贴底", () => {
    expect(
      isNearBottom({
        scrollHeight: 2000,
        scrollY: 2000 - 800 - PIN_THRESHOLD - 1,
        viewportHeight: 800,
      })
    ).toBe(false);
  });

  it("用户往上翻阅时不贴底", () => {
    // 距底 1200，远超阈值
    expect(isNearBottom({ scrollHeight: 2000, scrollY: 0, viewportHeight: 800 })).toBe(false);
  });

  it("过滚动（负距离，如 iOS 回弹）视为贴底", () => {
    expect(isNearBottom({ scrollHeight: 2000, scrollY: 1400, viewportHeight: 800 })).toBe(true);
  });

  it("内容短于视口时始终贴底", () => {
    expect(isNearBottom({ scrollHeight: 500, scrollY: 0, viewportHeight: 800 })).toBe(true);
  });

  it("支持自定义阈值", () => {
    const m = { scrollHeight: 2000, scrollY: 1150, viewportHeight: 800 }; // 距底 50
    expect(isNearBottom(m, 10)).toBe(false);
    expect(isNearBottom(m, 100)).toBe(true);
  });

  it("流式追加内容会让原本贴底的位置脱离贴底", () => {
    // 贴底状态
    const before = { scrollHeight: 2000, scrollY: 1200, viewportHeight: 800 };
    expect(isNearBottom(before)).toBe(true);

    // 文档因新 token 增高 500，滚动位置未变 → 距底 500，需要跟随
    const after = { ...before, scrollHeight: 2500 };
    expect(isNearBottom(after)).toBe(false);
  });
});

describe("resolvePinState", () => {
  it("到达底部即恢复跟随", () => {
    expect(
      resolvePinState({ atBottom: true, previousScrollY: 500, currentScrollY: 1200, wasPinned: false })
    ).toBe(true);
  });

  it("用户向上滚动则解除跟随", () => {
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 1200, currentScrollY: 600, wasPinned: true })
    ).toBe(false);
  });

  it("向下滚动但未到底部时保持原状态", () => {
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 600, currentScrollY: 900, wasPinned: true })
    ).toBe(true);
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 600, currentScrollY: 900, wasPinned: false })
    ).toBe(false);
  });

  it("内容增长导致的位置不变事件不应解除跟随", () => {
    // 这是修复的核心：文档增高后虽已不在底部，但用户没有向上滚动
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 1200, currentScrollY: 1200, wasPinned: true })
    ).toBe(true);
  });

  it("小于容差的抖动不解除跟随", () => {
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 1200, currentScrollY: 1199, wasPinned: true })
    ).toBe(true);
  });

  it("超出容差的向上滚动解除跟随", () => {
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 1200, currentScrollY: 1197, wasPinned: true })
    ).toBe(false);
  });

  it("解除跟随后向上继续滚动保持解除", () => {
    expect(
      resolvePinState({ atBottom: false, previousScrollY: 900, currentScrollY: 400, wasPinned: false })
    ).toBe(false);
  });
});

describe("distanceFromBottom", () => {
  it("计算距底距离", () => {
    expect(distanceFromBottom({ scrollHeight: 2000, scrollY: 1000, viewportHeight: 800 })).toBe(200);
  });

  it("过滚动时为负", () => {
    expect(distanceFromBottom({ scrollHeight: 2000, scrollY: 1300, viewportHeight: 800 })).toBe(-100);
  });
});

describe("resolveJumpButtonVisible", () => {
  it("明显滚离底部才出现", () => {
    expect(resolveJumpButtonVisible(JUMP_SHOW_THRESHOLD + 1, false)).toBe(true);
    expect(resolveJumpButtonVisible(JUMP_SHOW_THRESHOLD, false)).toBe(false);
  });

  it("已显示时需明显靠近底部才消失", () => {
    expect(resolveJumpButtonVisible(JUMP_HIDE_THRESHOLD + 1, true)).toBe(true);
    expect(resolveJumpButtonVisible(JUMP_HIDE_THRESHOLD, true)).toBe(false);
  });

  it("缓冲带内维持当前状态——这是防闪烁的关键", () => {
    // 两阈值之间的距离，显隐状态都不改变
    for (const d of [120, 180, 240, 259]) {
      expect(resolveJumpButtonVisible(d, false)).toBe(false);
      expect(resolveJumpButtonVisible(d, true)).toBe(true);
    }
  });

  it("在出现阈值附近来回抖动不会反复显隐", () => {
    let visible = false;
    // 模拟用户在 255~265 之间抖动
    const jitter = [255, 262, 258, 265, 259, 261];
    const transitions: boolean[] = [];
    for (const d of jitter) {
      const next = resolveJumpButtonVisible(d, visible);
      if (next !== visible) transitions.push(next);
      visible = next;
    }
    // 只允许发生一次状态变化（首次越过 260 后进入缓冲带，不再翻转）
    expect(transitions).toEqual([true]);
  });

  it("过滚动（负距离）时按钮隐藏", () => {
    expect(resolveJumpButtonVisible(-50, true)).toBe(false);
  });
});
