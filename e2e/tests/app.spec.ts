import { expect, test } from "@playwright/test";

test.describe("EW11 패킷 분석기", () => {
  test("실시간 모니터에 패킷이 스트리밍된다", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("nav.tabs")).toBeVisible();
    const rows = page.locator("table.pkt tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 20000 });
    await expect.poll(async () => rows.count(), { timeout: 20000 }).toBeGreaterThan(3);
    // hex content present
    await expect(rows.first().locator("td.hex")).toContainText(/[0-9A-F]{2} [0-9A-F]{2}/);
    // status chip shows demo mode
    await expect(page.locator("header.top")).toContainText("데모");
  });

  test("마커 기록 + 데모 이벤트 + 분석으로 이벤트 패밀리가 분류된다", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "이벤트 표시" }).click();

    // marker + simulated button press x3 for confidence
    for (let i = 0; i < 3; i++) {
      await page.getByTestId("mark-btn").click();
      await page.getByTestId("demo-light_on").click();
      await page.waitForTimeout(400);
    }
    await expect(page.locator(".marker-row")).toHaveCount(3);

    await page.getByRole("button", { name: "패킷 분석" }).click();
    await page.getByTestId("run-analysis").click();

    // family cards render
    const cards = page.locator(".family-card");
    await expect(cards.first()).toBeVisible({ timeout: 20000 });
    // the command family F70A01:10 (dst=HOST direction) classified as EVENT
    const eventCard = page.locator('[data-testid="family-F70A01:10"]');
    await expect(eventCard).toBeVisible();
    await expect(eventCard.locator(".badge")).toContainText("이벤트");
    // periodic broadcast family classified as IDLE
    const idleCard = page.locator('[data-testid="family-F70840:8"]');
    await expect(idleCard.locator(".badge")).toContainText("주기 신호");
    // expand a card -> bytemap renders byte cells
    await eventCard.locator(".family-head").click();
    await expect(eventCard.locator(".byte-cell").first()).toBeVisible();
    // diff section shows novel family
    await expect(page.locator(".card").last()).toContainText("마커별 차이 분석");
  });

  test("AI 리포트를 생성하고 다운로드할 수 있다", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "AI 리포트" }).click();
    await page.getByTestId("gen-report").click();
    const preview = page.getByTestId("report-preview");
    await expect(preview).toBeVisible({ timeout: 20000 });
    await expect(preview).toContainText("AI 분석 요청");
    await expect(preview).toContainText("패밀리 요약");

    const dl = page.waitForEvent("download");
    await page.getByRole("button", { name: "파일 다운로드" }).click();
    const file = await dl;
    expect(file.suggestedFilename()).toBe("ew11-report.md");
  });

  test("설정 탭에서 MQTT 설정을 저장할 수 있다", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "설정" }).click();
    await expect(page.locator("h3", { hasText: "MQTT 브로커" })).toBeVisible();
    const topicInput = page.locator(".card").first().locator("input.inp").nth(4);
    await topicInput.fill("ew11/#");
    await page.getByTestId("save-reconnect").click();
    await expect(page.locator(".toast")).toContainText("저장");
  });

  test("REST API가 응답한다", async ({ request }) => {
    const res = await request.get("/api/status");
    expect(res.ok()).toBeTruthy();
    const d = await res.json();
    expect(d.mode).toBe("demo");
    expect(d.total_packets).toBeGreaterThan(0);
  });
});
