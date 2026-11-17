(function (root) {
  "use strict";
  const formats = { clip: "Short clip", tutorial: "Tutorial / workshop", talk: "Conference talk", podcast: "Podcast / interview", other: "Other / unspecified" };
  const languageName = function (code) {
    if (!code || code === "und") return "Language unknown";
    try { return new Intl.DisplayNames(["en"], { type: "language" }).of(code); }
    catch (_) { return code; }
  };
  const matches = function (item, filters) {
    const topics = Array.isArray(item.topics) ? item.topics : String(item.topics || "").split(",");
    const isDotnet = item.aiRelevance === "dotnet" || topics.some(function (topic) { return topic.toLowerCase() === ".net"; });
    if (filters.relevance === "dotnet" && !isDotnet) return false;
    if (filters.relevance === "general" && isDotnet) return false;
    if (filters.language !== "all" && (item.language || "und") !== filters.language) return false;
    if (filters.format !== "all" && (item.contentType !== "video" || (item.videoFormat || "other") !== filters.format)) return false;
    if (filters.duration !== "all") {
      if (item.contentType !== "video") return false;
      const seconds = Number(item.durationSeconds) || null;
      if (filters.duration === "unknown") return seconds === null;
      if (seconds === null) return false;
      if (filters.duration === "short" && seconds >= 120) return false;
      if (filters.duration === "medium" && (seconds < 120 || seconds >= 1200)) return false;
      if (filters.duration === "long" && seconds < 1200) return false;
    }
    return true;
  };
  const api = { matches: matches, languageName: languageName, formats: formats };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NewsDiscovery = api;
})(typeof window === "undefined" ? globalThis : window);
