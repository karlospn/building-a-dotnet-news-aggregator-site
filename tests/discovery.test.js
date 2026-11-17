const test = require("node:test");
const assert = require("node:assert/strict");
const { matches } = require("../site/dotnetramblings/assets/js/discovery.js");
const filters = { relevance: "all", language: "all", duration: "all", format: "all" };
const video = { contentType: "video", topics: ["AI", ".NET"], aiRelevance: "dotnet", language: "es", durationSeconds: 119, videoFormat: "clip" };

test("filters combine relevance, language, duration, and format", () => {
  assert.ok(matches(video, { relevance: "dotnet", language: "es", duration: "short", format: "clip" }));
  assert.equal(matches(video, { ...filters, relevance: "general" }), false);
  assert.equal(matches(video, { ...filters, language: "en" }), false);
  assert.equal(matches(video, { ...filters, format: "tutorial" }), false);
});
test("duration boundaries and unknown lengths are distinct", () => {
  for (const [seconds, bucket] of [[119, "short"], [120, "medium"], [1199, "medium"], [1200, "long"], [null, "unknown"]]) {
    for (const choice of ["short", "medium", "long", "unknown"]) {
      assert.equal(matches({ ...video, durationSeconds: seconds }, { ...filters, duration: choice }), choice === bucket);
    }
  }
});
test("video-specific filters exclude articles without hiding them by default", () => {
  const article = { contentType: "article", topics: ["AI", ".NET"] };
  assert.ok(matches(article, filters));
  assert.equal(matches(article, { ...filters, duration: "unknown" }), false);
  assert.equal(matches(article, { ...filters, format: "other" }), false);
});
test("legacy cards use their topics and unknown metadata", () => {
  assert.ok(matches({ topics: "ai,.net", contentType: "video" }, { relevance: "dotnet", language: "und", duration: "unknown", format: "other" }));
});
