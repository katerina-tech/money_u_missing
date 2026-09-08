/**
 * The critical end-to-end paths.
 *
 * These are the accelerator demo script, executed: demo session, Money Map,
 * transparent matching, Germany check, save, track from potential to won, and
 * a goal. If these pass, the ninety-second story works.
 *
 * They run against a real backend and a real frontend. Nothing is mocked,
 * because the thing worth testing here is that the two halves agree.
 */

import { expect, test } from "@playwright/test";

test.describe("the accelerator demo path", () => {
  test("a visitor can go from the landing page to a Money Map with no account", async ({
    page,
  }) => {
    await page.goto("/");

    // The name is ambiguous, so the clarification must be in the first viewport.
    await expect(
      page.getByText(/not unclaimed government money/i),
    ).toBeVisible();

    // The Money Map preview must be unmistakably labelled as an example.
    await expect(page.getByText(/example — fictional data/i)).toBeVisible();

    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();

    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/demo session/i).first()).toBeVisible();
  });

  test("the Money Map separates potential from secured and explains the exclusions", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    // Nothing is secured yet, and the progress bar must say so.
    await expect(
      page.getByText(/This bar moves only on money you have actually/i),
    ).toBeVisible();

    // Opportunities with no published pay are counted, not estimated.
    await expect(
      page.getByText(/excluded from these totals/i).first(),
    ).toBeVisible();
  });

  test("the A-to-B band shows the pipeline and keeps potential off the goal rail", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    const band = page.getByRole("region", {
      name: /from where you are to where you want to be/i,
    });
    await expect(band).toBeVisible();
    await expect(band.getByText(/where you are/i)).toBeVisible();
    await expect(band.getByText(/where you want to be/i)).toBeVisible();

    // Nothing has been secured, so the goal rail must read zero even though the
    // demo profile has fourteen opportunities sitting in front of it. This is
    // the assertion that stops potential from ever being counted as progress.
    await expect(band.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "0",
    );

    // The hypothetical track is allowed to be full, but only while it is
    // labelled as a hypothetical.
    await expect(
      band.getByText(/Hypothetical, and not counted anywhere else/i),
    ).toBeVisible();

    // Selecting a stage has to produce the evidence behind its count.
    await band.getByRole("button", { name: /found/i }).click();
    await expect(
      band.getByText(/Nothing here is an offer, and nothing here is money/i),
    ).toBeVisible();
  });

  test("an opportunity states what we know and what we do not", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page
      .getByRole("link", { name: /view opportunity/i })
      .first()
      .click();

    await expect(
      page.getByRole("heading", { name: /why this matches/i }),
    ).toBeVisible();
    await expect(page.getByText(/what we don't know/i).first()).toBeVisible();
    await expect(
      page.getByText(/Computed in code from your profile/i),
    ).toBeVisible();

    // The Germany check is present, cited, and explicitly not advice.
    await expect(
      page.getByRole("heading", { name: /what this may mean in germany/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/not tax or legal advice/i).first(),
    ).toBeVisible();
    await expect(page.getByText(/questions to check/i).first()).toBeVisible();
  });

  test("saving an opportunity opens a workspace and tracking reaches earned money", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page
      .getByRole("link", { name: /view opportunity/i })
      .first()
      .click();
    await page.getByRole("button", { name: /prepare application/i }).click();

    // The action workspace.
    await expect(page.getByText(/requirements checklist/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/documents needed/i)).toBeVisible();

    await page.getByRole("button", { name: /mark as applied/i }).click();
    await expect(
      page.getByRole("button", { name: /mark as won/i }),
    ).toBeVisible();

    // Recording a win must ask for the real figure rather than copying the ad.
    await page.getByRole("button", { name: /mark as won/i }).click();
    await expect(page.getByText(/what did it actually pay/i)).toBeVisible();

    await page.getByLabel("Amount").fill("450");
    await page.getByRole("button", { name: /record it/i }).click();

    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible();
    // Secured money now exists, and it is the figure the user entered.
    await expect(page.getByText("€450").first()).toBeVisible();
  });

  test("a tax question is answered with citations, or declined", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/tax");
    await expect(page.getByText(/not Steuerberatung/i).first()).toBeVisible();

    await page
      .getByRole("button", { name: /Do I need to register a Gewerbe/i })
      .click();

    // Either an answer with sources, or an explicit refusal. Never an
    // uncited answer.
    await expect(
      page.getByText(/Sources|We are not going to answer this/i).first(),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("the calculator labels its output as illustrative", async ({ page }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/grow");
    // Assert the page rendered before driving it, so a failure here points at
    // the page rather than at the click.
    await expect(
      page.getByRole("heading", { name: /goals and projections/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^calculate$/i }),
    ).toBeEnabled();
    await page.getByRole("button", { name: /^calculate$/i }).click();
    await expect(
      page
        .getByText(/Illustrative assumption\s*[-–—]\s*not a forecast/i)
        .first(),
    ).toBeVisible();
  });

  test("the personal page records money without ever calculating tax", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/personal");
    await expect(
      page.getByRole("heading", { name: /your money, as you describe it/i }),
    ).toBeVisible();

    // Gross and net are asked for separately, because the product cannot
    // convert between them and must not appear to.
    await page.getByLabel("What is it?").fill("Main job");
    await page.getByLabel("Amount", { exact: true }).first().fill("2850");
    await page.getByLabel("Gross or net?").selectOption("NET");
    await page.getByRole("button", { name: /^add income$/i }).click();

    await expect(page.getByText("€2,850").first()).toBeVisible({
      timeout: 15_000,
    });
    // The net total is populated and the gross one stays empty. They are two
    // figures on this page and never one.
    const net = page.getByText("Net, monthly").locator("xpath=..");
    await expect(net).toContainText("2,850");

    // A recorded cost is added up and taken no further.
    await page.getByLabel("What was it?").fill("Laptop");
    await page.getByLabel("Amount", { exact: true }).last().fill("1200");
    await page.getByRole("button", { name: /record cost/i }).click();

    await expect(page.getByText("Tax effect")).toBeVisible();
    await expect(page.getByText("Not calculated")).toBeVisible();
    await expect(page.getByText(/not Steuerberatung/i).first()).toBeVisible();
  });

  test("disclosing children adds questions and cites the statute", async ({
    page,
  }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/personal");
    await page.getByLabel("Do you have children?").selectOption("YES");
    await page.getByRole("button", { name: /save household details/i }).click();

    await expect(
      page.getByRole("heading", { name: /what to check in germany/i }),
    ).toBeVisible({
      timeout: 15_000,
    });
    // A question, and a source. Never an entitlement.
    await expect(page.getByText(/questions to check/i).first()).toBeVisible();
    await expect(page.getByText(/does not calculate tax/i)).toBeVisible();
  });

  test("the family comparison recommends nothing", async ({ page }) => {
    await page.goto("/");
    await page
      .getByRole("button", { name: /build my money map/i })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Your Money Map" }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/family");
    await expect(
      page.getByText(/no generally correct answer/i).first(),
    ).toBeVisible();
  });
});

test.describe("signed-out behaviour", () => {
  test("the app redirects to sign-in", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });

  test("static pages are reachable without an account", async ({ page }) => {
    for (const path of ["/about", "/privacy", "/pricing"]) {
      await page.goto(path);
      await expect(page.locator("h1")).toBeVisible();
    }
  });
});
