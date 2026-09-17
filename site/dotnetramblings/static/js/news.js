(function () {
  "use strict";

  const storage = {
    get(key, fallback) {
      try {
        return JSON.parse(localStorage.getItem(key)) ?? fallback;
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch {
        // Preferences remain available for the current page when storage is blocked.
      }
    }
  };

  const grid = document.querySelector("#news-grid");
  const allCards = Array.from(document.querySelectorAll("[data-news-card]"));
  const cards = grid ? Array.from(grid.querySelectorAll("[data-news-card]")) : [];

  if (cards.length && grid) {
    const storedArray = function (key) {
      const value = storage.get(key, []);
      return Array.isArray(value) ? value : [];
    };
    let bookmarks = new Set(storedArray("newsBookmarks"));
    let readStories = new Set(storedArray("newsReadStories"));
    let hiddenSources = new Set(storedArray("newsHiddenSources"));
    let activeType =
      location.hash === "#bookmarks" ? "bookmarks" : storage.get("newsActiveType", "all");
    let activeTopic = storage.get("newsActiveTopic", "all");
    let query = "";

    const updateCards = function () {
      let visible = 0;
      allCards.forEach(function (card) {
        const url = card.dataset.url;
        const topics = card.dataset.topics.split(",");
        const isFilterable = grid.contains(card);
        const matchesType =
          activeType === "all" ||
          card.dataset.contentType === activeType ||
          (activeType === "bookmarks" && bookmarks.has(url));
        const matchesTopic = activeTopic === "all" || topics.includes(activeTopic);
        const matchesSearch = !query || card.textContent.toLowerCase().includes(query);
        const matchesFilters = matchesType && matchesTopic && matchesSearch;
        const isVisible =
          !hiddenSources.has(card.dataset.source) && (!isFilterable || matchesFilters);

        card.hidden = !isVisible;
        card.classList.toggle("is-filtered-out", !isVisible);
        card.classList.toggle("is-read", readStories.has(url));
        const bookmarkButton = card.querySelector("[data-bookmark]");
        bookmarkButton.classList.toggle("is-bookmarked", bookmarks.has(url));
        bookmarkButton.textContent = bookmarks.has(url) ? "★" : "☆";
        bookmarkButton.setAttribute("aria-pressed", String(bookmarks.has(url)));
        if (isVisible && isFilterable) visible += 1;
      });

      const count = document.querySelector("#visible-count");
      if (count) count.textContent = `${visible} stories on this page`;
      const empty = document.querySelector("#empty-state");
      if (empty) empty.hidden = visible !== 0;
    };

    document.addEventListener("click", function (event) {
      const typeButton = event.target.closest("[data-type-filter]");
      if (typeButton) {
        activeType = typeButton.dataset.typeFilter;
        storage.set("newsActiveType", activeType);
        document.querySelectorAll("[data-type-filter]").forEach(function (button) {
          button.classList.toggle("is-active", button === typeButton);
        });
        if (activeType === "bookmarks") history.replaceState(null, "", "#bookmarks");
        else if (location.hash === "#bookmarks") history.replaceState(null, "", location.pathname);
        updateCards();
      }

      const topicButton = event.target.closest("[data-topic-filter]");
      if (topicButton) {
        activeTopic = topicButton.dataset.topicFilter;
        storage.set("newsActiveTopic", activeTopic);
        document.querySelectorAll("[data-topic-filter]").forEach(function (button) {
          button.classList.toggle("is-active", button.dataset.topicFilter === activeTopic);
        });
        updateCards();
      }

      const bookmarkButton = event.target.closest("[data-bookmark]");
      if (bookmarkButton) {
        const card = bookmarkButton.closest("[data-news-card]");
        const url = card.dataset.url;
        if (bookmarks.has(url)) bookmarks.delete(url);
        else bookmarks.add(url);
        storage.set("newsBookmarks", Array.from(bookmarks));
        updateCards();
      }

      const hideButton = event.target.closest("[data-hide-source]");
      if (hideButton) {
        const source = hideButton.closest("[data-news-card]").dataset.source;
        hiddenSources.add(source);
        storage.set("newsHiddenSources", Array.from(hiddenSources));
        updateCards();
      }

      const shareButton = event.target.closest("[data-share]");
      if (shareButton) {
        const card = shareButton.closest("[data-news-card]");
        const title = card.querySelector("h3").textContent.trim();
        if (navigator.share) {
          navigator.share({ title: title, url: card.dataset.url }).catch(function () {});
        } else if (navigator.clipboard) {
          navigator.clipboard.writeText(card.dataset.url);
          shareButton.textContent = "Copied";
          window.setTimeout(function () {
            shareButton.textContent = "Share";
          }, 1500);
        }
      }

      const outbound = event.target.closest("[data-outbound]");
      if (outbound) {
        const card = outbound.closest("[data-news-card]");
        readStories.add(card.dataset.url);
        storage.set("newsReadStories", Array.from(readStories));
        card.classList.add("is-read");
        if (typeof window.gtag === "function") {
          window.gtag("event", "outbound_story_click", {
            source_id: card.dataset.source,
            content_type: card.dataset.contentType,
            story_url: card.dataset.url
          });
        }
      }

      if (event.target.closest("[data-reset-preferences]")) {
        hiddenSources = new Set();
        storage.set("newsHiddenSources", []);
        updateCards();
      }
    });

    const search = document.querySelector("[data-news-search]");
    if (search) {
      search.addEventListener("input", function () {
        query = search.value.trim().toLowerCase();
        updateCards();
      });
    }

    const density = document.querySelector("[data-density]");
    if (density) {
      const savedDensity = storage.get("newsDensity", "comfortable");
      density.value = savedDensity;
      grid.classList.toggle("is-compact", savedDensity === "compact");
      density.addEventListener("change", function () {
        storage.set("newsDensity", density.value);
        grid.classList.toggle("is-compact", density.value === "compact");
      });
    }

    const savedTypeButton = document.querySelector(`[data-type-filter="${activeType}"]`);
    if (savedTypeButton) savedTypeButton.classList.add("is-active");
    document.querySelectorAll("[data-type-filter]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.typeFilter === activeType);
    });
    document.querySelectorAll("[data-topic-filter]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.topicFilter === activeTopic);
    });
    updateCards();
  }

  document.querySelectorAll("[data-relative-time]").forEach(function (element) {
    const timestamp = new Date(element.dateTime).getTime();
    if (Number.isNaN(timestamp)) return;
    const seconds = Math.round((timestamp - Date.now()) / 1000);
    const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    const ranges = [
      ["year", 31536000],
      ["month", 2592000],
      ["week", 604800],
      ["day", 86400],
      ["hour", 3600],
      ["minute", 60]
    ];
    const range = ranges.find(function (candidate) {
      return Math.abs(seconds) >= candidate[1];
    }) || ["minute", 60];
    element.textContent = formatter.format(Math.round(seconds / range[1]), range[0]);
  });

  document.querySelectorAll("[data-fallback-image]").forEach(function (image) {
    const useFallback = function () {
      image.src = image.dataset.fallbackImage;
      image.removeAttribute("data-fallback-image");
    };
    image.addEventListener("error", useFallback, { once: true });
    if (image.complete && image.naturalWidth === 0) useFallback();
  });

  const feedCards = Array.from(document.querySelectorAll("[data-feed-card]"));
  if (feedCards.length) {
    let feedType = "all";
    let feedQuery = "";
    const updateFeeds = function () {
      let visible = 0;
      feedCards.forEach(function (card) {
        const show =
          (feedType === "all" || card.dataset.feedType === feedType) &&
          (!feedQuery || card.textContent.toLowerCase().includes(feedQuery));
        card.hidden = !show;
        card.classList.toggle("is-filtered-out", !show);
        if (show) visible += 1;
      });
      const empty = document.querySelector("[data-feed-empty]");
      if (empty) empty.hidden = visible !== 0;
    };

    const feedSearch = document.querySelector("[data-feed-search]");
    if (feedSearch) {
      feedSearch.addEventListener("input", function (event) {
        feedQuery = event.target.value.trim().toLowerCase();
        updateFeeds();
      });
    }
    document.querySelectorAll("[data-feed-type]").forEach(function (button) {
      button.addEventListener("click", function () {
        feedType = button.dataset.feedType;
        document.querySelectorAll("[data-feed-type]").forEach(function (candidate) {
          candidate.classList.toggle("is-active", candidate === button);
        });
        updateFeeds();
      });
    });
  }
})();
