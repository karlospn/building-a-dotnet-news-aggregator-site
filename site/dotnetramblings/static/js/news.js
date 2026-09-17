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

  const escapeHtml = function (value) {
    const element = document.createElement("div");
    element.textContent = value == null ? "" : String(value);
    return element.innerHTML;
  };

  const externalUrl = function (value) {
    try {
      const url = new URL(value, window.location.origin);
      return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
    } catch {
      return "#";
    }
  };

  const imageUrl = function (value) {
    if (!value) return "/images/misc.png";
    if (/^https?:\/\//i.test(value)) return externalUrl(value);
    return `/${String(value).replace(/^\/+/, "")}`;
  };

  const relativeTime = function (date) {
    const timestamp = new Date(date).getTime();
    if (Number.isNaN(timestamp)) return "";
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
    return formatter.format(Math.round(seconds / range[1]), range[0]);
  };

  const renderArchiveCard = function (item) {
    const type = item.contentType === "video" ? "video" : "article";
    const source = item.source || "Unknown source";
    const sourceId = item.sourceId || source.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const topics = Array.isArray(item.topics) && item.topics.length ? item.topics : ["General"];
    const topicIds = topics.map(function (topic) {
      return String(topic).toLowerCase().replace(/\s+/g, "-");
    });
    const link = externalUrl(item.link);
    const thumbnail = imageUrl(item.thumbnail);
    const metadata = [
      relativeTime(item.date),
      item.readingMinutes ? `${item.readingMinutes} min read` : ""
    ].filter(Boolean).join(" · ");
    const topicMarkup = topics.map(function (topic, index) {
      return `<button type="button" class="topic-badge" data-topic-filter="${escapeHtml(topicIds[index])}">${escapeHtml(topic)}</button>`;
    }).join("");

    return `
      <article class="news-card" data-news-card data-url="${escapeHtml(link)}"
        data-source="${escapeHtml(sourceId)}" data-topics="${escapeHtml(topicIds.join(","))}"
        data-content-type="${type}" data-date="${escapeHtml(item.date)}">
        <a class="news-card__image" href="${escapeHtml(link)}" data-outbound>
          <img src="${escapeHtml(thumbnail)}" alt="" loading="lazy" referrerpolicy="no-referrer"
            data-fallback-image="/images/misc.png">
          <span class="content-badge">${type === "video" ? "▶ Video" : "Article"}</span>
          ${item.duration ? `<span class="duration-badge">${escapeHtml(item.duration)}</span>` : ""}
        </a>
        <div class="news-card__body">
          <div class="source-line">
            <span>${escapeHtml(source)}${item.author ? ` · ${escapeHtml(item.author)}` : ""}</span>
            <span>${escapeHtml(metadata)}</span>
          </div>
          <h3><a href="${escapeHtml(link)}" data-outbound>${escapeHtml(item.title)}</a></h3>
          <div class="topic-list">${topicMarkup}</div>
          <p class="news-card__summary">${escapeHtml(item.summary || "")}</p>
          ${item.whyItMatters ? `<p class="why-it-matters"><strong>Why it matters:</strong> ${escapeHtml(item.whyItMatters)}</p>` : ""}
          <div class="news-card__footer">
            <a href="${escapeHtml(link)}" class="story-link" data-outbound>
              ${type === "video" ? "Watch" : "Read"} on ${escapeHtml(source)} →
            </a>
            <div class="card-actions">
              <button type="button" data-bookmark aria-label="Bookmark ${escapeHtml(item.title)}">☆</button>
              <button type="button" data-share aria-label="Share ${escapeHtml(item.title)}">Share</button>
              <button type="button" data-hide-source aria-label="Hide stories from ${escapeHtml(source)}">Hide</button>
            </div>
          </div>
        </div>
      </article>`;
  };

  document.addEventListener("error", function (event) {
    const image = event.target;
    if (image instanceof HTMLImageElement && image.dataset.fallbackImage) {
      image.src = image.dataset.fallbackImage;
      image.removeAttribute("data-fallback-image");
    }
  }, true);

  const grid = document.querySelector("#news-grid");
  let cards = grid ? Array.from(grid.querySelectorAll("[data-news-card]")) : [];
  const featuredCards = Array.from(
    document.querySelectorAll(".featured-grid [data-news-card]")
  );

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
    let archiveItems = null;
    let currentPage = 1;
    const pageSize = Number(grid.dataset.pageSize) || cards.length;
    const contentScope = grid.dataset.contentScope || "";
    const pagination = document.querySelector("[data-client-pagination]");
    const weekSelect = document.querySelector("[data-week-select]");
    let selectedWeek = null;

    if (!["all", "article", "video", "bookmarks"].includes(activeType)) activeType = "all";
    const topicControls = Array.from(
      document.querySelectorAll(".discovery-panel [data-topic-filter]")
    );
    if (
      activeTopic !== "all" &&
      topicControls.length &&
      !topicControls.some(function (button) {
        return button.dataset.topicFilter === activeTopic;
      })
    ) {
      activeTopic = "all";
    }

    const weekKey = function (value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "";
      const dayFromMonday = (date.getUTCDay() + 6) % 7;
      date.setUTCDate(date.getUTCDate() - dayFromMonday);
      date.setUTCHours(0, 0, 0, 0);
      return date.toISOString().slice(0, 10);
    };

    const populateWeeks = function (items) {
      if (!weekSelect) return;
      const weeks = Array.from(
        new Set(items.map(function (item) {
          return weekKey(item.date);
        }).filter(Boolean))
      ).sort().reverse();
      const requestedWeek = new URLSearchParams(location.search).get("week");
      selectedWeek = weeks.includes(requestedWeek) ? requestedWeek : weeks[0] || null;
      const formatter = new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC"
      });
      weekSelect.innerHTML = weeks.map(function (week) {
        const start = new Date(`${week}T00:00:00Z`);
        const end = new Date(start);
        end.setUTCDate(end.getUTCDate() + 6);
        const label = `${formatter.format(start)} – ${formatter.format(end)}`;
        return `<option value="${week}">${escapeHtml(label)}</option>`;
      }).join("");
      if (selectedWeek) weekSelect.value = selectedWeek;
    };

    const matchesFilters = function (item) {
      const topics = Array.isArray(item.topics)
        ? item.topics.map(function (topic) {
            return String(topic).toLowerCase().replace(/\s+/g, "-");
          })
        : String(item.topics || "").split(",");
      const text = [
        item.title,
        item.source,
        item.author,
        item.summary,
        topics.join(" ")
      ].join(" ").toLowerCase();
      const matchesType =
        activeType === "all" ||
        item.contentType === activeType ||
        (activeType === "bookmarks" && bookmarks.has(item.link));
      return (
        (!contentScope || item.contentType === contentScope) &&
        matchesType &&
        (activeTopic === "all" || topics.includes(activeTopic)) &&
        (!selectedWeek || weekKey(item.date) === selectedWeek) &&
        (!query || text.includes(query)) &&
        !hiddenSources.has(item.sourceId)
      );
    };

    const updateCardState = function (card) {
      const url = card.dataset.url;
      card.classList.toggle("is-read", readStories.has(url));
      const bookmarkButton = card.querySelector("[data-bookmark]");
      if (bookmarkButton) {
        bookmarkButton.classList.toggle("is-bookmarked", bookmarks.has(url));
        bookmarkButton.textContent = bookmarks.has(url) ? "★" : "☆";
        bookmarkButton.setAttribute("aria-pressed", String(bookmarks.has(url)));
      }
    };

    const updateFeaturedCards = function () {
      featuredCards.forEach(function (card) {
        const isVisible = !hiddenSources.has(card.dataset.source);
        card.hidden = !isVisible;
        card.classList.toggle("is-filtered-out", !isVisible);
        updateCardState(card);
      });
    };

    const renderArchive = function () {
      const matches = archiveItems.filter(matchesFilters);
      const pageCount = Math.max(1, Math.ceil(matches.length / pageSize));
      currentPage = Math.min(currentPage, pageCount);
      const start = (currentPage - 1) * pageSize;
      grid.innerHTML = matches.slice(start, start + pageSize).map(renderArchiveCard).join("");
      cards = Array.from(grid.querySelectorAll("[data-news-card]"));
      cards.forEach(updateCardState);
      updateFeaturedCards();

      const count = document.querySelector("#visible-count");
      if (count) count.textContent = String(matches.length);
      const renderedCount = document.querySelector("#rendered-count");
      if (renderedCount) {
        renderedCount.textContent = String(Math.min(pageSize, matches.length - start));
      }
      const digestCount = document.querySelector("[data-digest-count]");
      if (digestCount) digestCount.textContent = String(matches.length);
      const empty = document.querySelector("#empty-state");
      if (empty) empty.hidden = matches.length !== 0;
      if (pagination) {
        pagination.hidden = matches.length <= pageSize;
        pagination.querySelector("[data-page-previous]").disabled = currentPage === 1;
        pagination.querySelector("[data-page-next]").disabled = currentPage === pageCount;
        pagination.querySelector("[data-page-status]").textContent =
          `Page ${currentPage} of ${pageCount}`;
      }
    };

    const updateCards = function () {
      if (archiveItems) {
        renderArchive();
        return;
      }

      updateFeaturedCards();
      let visible = 0;
      cards.forEach(function (card) {
        const item = {
          title: card.textContent,
          source: card.dataset.source,
          sourceId: card.dataset.source,
          contentType: card.dataset.contentType,
          topics: card.dataset.topics,
          link: card.dataset.url
        };
        const isVisible = matchesFilters(item);
        card.hidden = !isVisible;
        card.classList.toggle("is-filtered-out", !isVisible);
        updateCardState(card);
        if (isVisible) visible += 1;
      });

      const count = document.querySelector("#visible-count");
      if (count) count.textContent = String(visible);
      const renderedCount = document.querySelector("#rendered-count");
      if (renderedCount) renderedCount.textContent = String(visible);
      const empty = document.querySelector("#empty-state");
      if (empty) empty.hidden = visible !== 0;
    };

    document.addEventListener("click", function (event) {
      const typeButton = event.target.closest("[data-type-filter]");
      if (typeButton) {
        activeType = typeButton.dataset.typeFilter;
        currentPage = 1;
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
        currentPage = 1;
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
        currentPage = 1;
        updateCards();
      }

      if (event.target.closest("[data-page-previous]") && currentPage > 1) {
        currentPage -= 1;
        renderArchive();
        grid.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      if (event.target.closest("[data-page-next]")) {
        currentPage += 1;
        renderArchive();
        grid.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });

    const search = document.querySelector("[data-news-search]");
    if (search) {
      search.addEventListener("input", function () {
        query = search.value.trim().toLowerCase();
        currentPage = 1;
        updateCards();
      });
    }

    if (weekSelect) {
      weekSelect.addEventListener("change", function () {
        selectedWeek = weekSelect.value;
        currentPage = 1;
        const url = new URL(location.href);
        url.searchParams.set("week", selectedWeek);
        history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
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

    document.querySelectorAll("[data-type-filter]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.typeFilter === activeType);
    });
    document.querySelectorAll("[data-topic-filter]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.topicFilter === activeTopic);
    });
    updateCards();

    if (grid.dataset.archiveUrl && typeof window.fetch === "function") {
      window.fetch(grid.dataset.archiveUrl, { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok) throw new Error(`Archive request failed: ${response.status}`);
          return response.json();
        })
        .then(function (items) {
          if (!Array.isArray(items)) throw new Error("Archive response is not an array");
          archiveItems = items;
          populateWeeks(items);
          currentPage = 1;
          updateCards();
        })
        .catch(function (error) {
          console.warn("Using the current page because the archive could not be loaded.", error);
        });
    }
  }

  document.querySelectorAll("[data-relative-time]").forEach(function (element) {
    element.textContent = relativeTime(element.dateTime);
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
