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

  const visitBaseline = function () {
    const now = Date.now();
    const fallback = now - 24 * 60 * 60 * 1000;
    try {
      const sessionBaseline = sessionStorage.getItem("newsVisitBaseline");
      if (sessionBaseline) return Number(sessionBaseline);
      const previousVisit = Number(storage.get("newsLastVisit", fallback));
      const baseline = Number.isFinite(previousVisit) ? previousVisit : fallback;
      sessionStorage.setItem("newsVisitBaseline", String(baseline));
      storage.set("newsLastVisit", now);
      return baseline;
    } catch {
      return fallback;
    }
  }();

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

  const setButtonFeedback = function (button, message) {
    const originalText = button.textContent;
    button.textContent = message;
    window.setTimeout(function () {
      button.textContent = originalText;
    }, 1500);
  };

  const copyLink = async function (value) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return true;
      } catch {
        // Fall through for browsers that deny the asynchronous clipboard API.
      }
    }

    const input = document.createElement("textarea");
    input.value = value;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch {
      copied = false;
    }
    input.remove();
    return copied;
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
    const aiSubtopics = Array.isArray(item.aiSubtopics) ? item.aiSubtopics : [];
    const topicIds = topics.map(function (topic) {
      return String(topic).toLowerCase().replace(/\s+/g, "-");
    });
    const link = externalUrl(item.link);
    const thumbnail = imageUrl(item.thumbnail);
    const fallbackThumbnail = imageUrl(item.fallbackThumbnail || "images/topics/general.svg");
    const metadata = [
      relativeTime(item.date),
      item.readingMinutes ? `${item.readingMinutes} min read` : ""
    ].filter(Boolean).join(" · ");
    const topicMarkup = topics.slice(0, 2).map(function (topic, index) {
      return `<button type="button" class="topic-badge" data-topic-filter="${escapeHtml(topicIds[index])}">${escapeHtml(topic)}</button>`;
    }).join("");
    const encodedLink = encodeURIComponent(link);
    const encodedTitle = encodeURIComponent(item.title || "");
    const summary = String(item.summary || "");
    const summaryText = summary.length > 180
      ? `${summary.slice(0, 177).trimEnd()}…`
      : summary;

    return `
      <article class="news-card" data-news-card data-url="${escapeHtml(link)}"
        data-source="${escapeHtml(sourceId)}" data-topics="${escapeHtml(topicIds.join(","))}"
        data-ai-subtopics="${escapeHtml(aiSubtopics.map(function (value) {
          return String(value).toLowerCase().replace(/\s+/g, "-");
        }).join(","))}"
        data-content-type="${type}" data-date="${escapeHtml(item.date)}">
        <a class="news-card__image" href="${escapeHtml(link)}" data-outbound>
          <img src="${escapeHtml(thumbnail)}" alt="" width="640" height="360" loading="lazy"
            decoding="async" referrerpolicy="no-referrer"
            data-fallback-image="${escapeHtml(fallbackThumbnail)}">
          ${type === "video" ? '<span class="content-badge">▶</span>' : ""}
          ${item.duration ? `<span class="duration-badge">${escapeHtml(item.duration)}</span>` : ""}
        </a>
        <div class="news-card__body">
          <div class="source-line">
            <span>${escapeHtml(source)}</span>
            <span>${escapeHtml(metadata)}</span>
          </div>
          <h3><a href="${escapeHtml(link)}" data-outbound>${escapeHtml(item.title)}</a></h3>
          <div class="topic-list">${topicMarkup}</div>
          <p class="news-card__summary">${escapeHtml(summaryText)}</p>
          <div class="news-card__footer">
            <a href="${escapeHtml(link)}" class="story-link" data-outbound>
              ${type === "video" ? "Watch video" : "Read article"} →
            </a>
            <div class="card-actions">
              <button type="button" data-bookmark aria-label="Bookmark ${escapeHtml(item.title)}">☆</button>
              <details class="share-control">
                <summary aria-label="More actions">•••</summary>
                <div class="share-menu">
                  <div class="share-menu__header">
                    <strong>Share</strong>
                    <button type="button" data-close-share aria-label="Close share menu">×</button>
                  </div>
                  <a href="https://www.linkedin.com/sharing/share-offsite/?url=${encodedLink}" target="_blank" rel="noopener">LinkedIn</a>
                  <a href="https://twitter.com/intent/tweet?url=${encodedLink}&text=${encodedTitle}" target="_blank" rel="noopener">X</a>
                  <a href="mailto:?subject=${encodedTitle}&body=${encodedLink}">Email</a>
                  <button type="button" data-copy-link>Copy link</button>
                  <button type="button" data-hide-source>Hide ${escapeHtml(source)}</button>
                </div>
              </details>
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

  const mediaQuery = function (query) {
    return typeof window.matchMedia === "function"
      ? window.matchMedia(query)
      : { matches: false };
  };
  const reducedMotion = mediaQuery("(prefers-reduced-motion: reduce)");
  const mobileViewport = mediaQuery("(max-width: 620px)");
  const filterDisclosures = Array.from(
    document.querySelectorAll(".filter-disclosure")
  );
  const hubSections = Array.from(
    document.querySelectorAll("[data-hub-section]")
  );
  hubSections.forEach(function (section) {
    const key = `aiHubSection:${section.dataset.hubSection}`;
    try {
      const stored = sessionStorage.getItem(key);
      if (stored !== null) section.open = stored === "open";
      section.addEventListener("toggle", function () {
        sessionStorage.setItem(key, section.open ? "open" : "closed");
      });
    } catch {
      // Native details behavior remains available when storage is blocked.
    }
  });
  const syncFilterDisclosures = function () {
    filterDisclosures.forEach(function (disclosure) {
      disclosure.open = !mobileViewport.matches;
    });
  };
  syncFilterDisclosures();
  if (mobileViewport.addEventListener) {
    mobileViewport.addEventListener("change", syncFilterDisclosures);
  }

  const scrollToGrid = function (grid) {
    grid.scrollIntoView({
      behavior: reducedMotion.matches ? "auto" : "smooth",
      block: "start"
    });
  };

  const grid = document.querySelector("#news-grid");
  let cards = grid ? Array.from(grid.querySelectorAll("[data-news-card]")) : [];
  const featuredCards = Array.from(
    document.querySelectorAll(".featured-grid [data-news-card]")
  );

  if (grid) {
    const storedArray = function (key) {
      const value = storage.get(key, []);
      return Array.isArray(value) ? value : [];
    };
    let bookmarks = new Set(storedArray("newsBookmarks"));
    let readStories = new Set(storedArray("newsReadStories"));
    let hiddenSources = new Set(storedArray("newsHiddenSources"));
    const defaultType = grid.dataset.defaultType || "all";
    let activeType =
      location.hash === "#bookmarks"
        ? "bookmarks"
        : defaultType;
    let previousType = activeType === "bookmarks" ? defaultType : activeType;
    let activeTopic = "all";
    let activeAISubtopic = "all";
    let showNew = false;
    let query = "";
    let archiveItems = null;
    let currentPage = 1;
    const pageSize = Number(grid.dataset.pageSize) || cards.length;
    const contentScope = grid.dataset.contentScope || "";
    const topicScope = grid.dataset.topicScope || "";
    const pagination = document.querySelector("[data-client-pagination]");
    const weekSelect = document.querySelector("[data-week-select]");
    const typeSelect = document.querySelector("[data-type-select]");
    const topicSelect = document.querySelector("[data-topic-select]");
    const aiSubtopicSelect = document.querySelector("[data-ai-subtopic-select]");
    let selectedWeek = null;
    const newFilterButton = document.querySelector("[data-new-filter]");

    if (!["all", "article", "video", "bookmarks"].includes(activeType)) activeType = "all";
    if (contentScope && activeType !== "bookmarks") activeType = "all";
    const availableTopics = topicSelect
      ? Array.from(topicSelect.options).map(function (option) {
          return option.value;
        })
      : [];
    if (activeTopic !== "all" && availableTopics.length && !availableTopics.includes(activeTopic)) {
      activeTopic = "all";
    }
    const requestedTopic = new URLSearchParams(location.search).get("topic");
    if (requestedTopic && availableTopics.includes(requestedTopic)) {
      activeTopic = requestedTopic;
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

    const populateAISubtopics = function (items) {
      if (!aiSubtopicSelect) return;
      const scopedItems = items.filter(function (item) {
        return (item.topics || []).map(function (topic) {
          return String(topic).toLowerCase().replace(/\s+/g, "-");
        }).includes(topicScope || "ai");
      });
      const hubItemCount = document.querySelector("[data-hub-item-count]");
      if (hubItemCount) hubItemCount.textContent = String(scopedItems.length);
      Array.from(aiSubtopicSelect.options).forEach(function (option) {
        if (option.value === "all") {
          option.textContent = `All AI (${scopedItems.length})`;
          return;
        }
        const count = scopedItems.filter(function (item) {
          return (item.aiSubtopics || []).map(function (value) {
            return String(value).toLowerCase().replace(/\s+/g, "-");
          }).includes(option.value);
        }).length;
        const label = option.dataset.label || option.textContent;
        option.dataset.label = label;
        option.textContent = `${label} (${count})`;
        option.disabled = count === 0;
      });
    };

    const matchesFilters = function (item) {
      const topics = Array.isArray(item.topics)
        ? item.topics.map(function (topic) {
            return String(topic).toLowerCase().replace(/\s+/g, "-");
          })
        : String(item.topics || "").split(",");
      const aiSubtopics = Array.isArray(item.aiSubtopics)
        ? item.aiSubtopics.map(function (value) {
            return String(value).toLowerCase().replace(/\s+/g, "-");
          })
        : String(item.aiSubtopics || "").split(",").filter(Boolean);
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
        (!topicScope || topics.includes(topicScope)) &&
        matchesType &&
        (activeTopic === "all" || topics.includes(activeTopic)) &&
        (activeAISubtopic === "all" || aiSubtopics.includes(activeAISubtopic)) &&
        (!selectedWeek || weekKey(item.date) === selectedWeek) &&
        (!showNew || new Date(item.date).getTime() > visitBaseline) &&
        (!query || text.includes(query)) &&
        !hiddenSources.has(item.sourceId)
      );
    };

    const updateCardState = function (card) {
      const url = card.dataset.url;
      card.classList.toggle("is-read", readStories.has(url));
      card.classList.toggle(
        "is-new",
        new Date(card.dataset.date).getTime() > visitBaseline
      );
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
      const resultLabel = document.querySelector("#result-label");
      if (resultLabel) {
        resultLabel.textContent =
          contentScope === "video" || activeType === "video"
            ? "videos"
            : activeType === "article"
              ? "articles"
              : "stories";
      }
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
      updateNewCount(archiveItems);
    };

    const updateNewCount = function (items) {
      if (!newFilterButton) return;
      const count = items.filter(function (item) {
        return (
          (!contentScope || item.contentType === contentScope) &&
          (!topicScope || (item.topics || []).map(function (topic) {
            return String(topic).toLowerCase().replace(/\s+/g, "-");
          }).includes(topicScope)) &&
          (
            activeAISubtopic === "all"
            || (item.aiSubtopics || []).map(function (value) {
              return String(value).toLowerCase().replace(/\s+/g, "-");
            }).includes(activeAISubtopic)
          ) &&
          (!selectedWeek || weekKey(item.date) === selectedWeek) &&
          new Date(item.date).getTime() > visitBaseline
        );
      }).length;
      const countElement = newFilterButton.querySelector("[data-new-count]");
      if (countElement) countElement.textContent = count ? String(count) : "";
      newFilterButton.hidden = count === 0 && !showNew;
      newFilterButton.disabled = count === 0;
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
          aiSubtopics: card.dataset.aiSubtopics,
          link: card.dataset.url,
          date: card.dataset.date
        };
        const isVisible = matchesFilters(item);
        card.hidden = !isVisible;
        card.classList.toggle("is-filtered-out", !isVisible);
        updateCardState(card);
        if (isVisible) visible += 1;
      });

      const count = document.querySelector("#visible-count");
      if (count) count.textContent = String(visible);
      const resultLabel = document.querySelector("#result-label");
      if (resultLabel) {
        resultLabel.textContent =
          contentScope === "video" || activeType === "video"
            ? "videos"
            : activeType === "article"
              ? "articles"
              : "stories";
      }
      const renderedCount = document.querySelector("#rendered-count");
      if (renderedCount) renderedCount.textContent = String(visible);
      const empty = document.querySelector("#empty-state");
      if (empty) empty.hidden = visible !== 0;
    };

    document.addEventListener("click", function (event) {
      const closeShareButton = event.target.closest("[data-close-share]");
      if (closeShareButton) {
        closeShareButton.closest("details").open = false;
      } else if (!event.target.closest(".share-control")) {
        document.querySelectorAll(".share-control[open]").forEach(function (menu) {
          menu.open = false;
        });
      }

      const closeSettingsButton = event.target.closest("[data-close-settings]");
      if (closeSettingsButton) {
        closeSettingsButton.closest("details").open = false;
      } else if (!event.target.closest(".browser-settings")) {
        document.querySelectorAll(".browser-settings[open]").forEach(function (settings) {
          settings.open = false;
        });
      }

      const typeButton = event.target.closest("[data-type-filter]");
      if (typeButton) {
        if (typeButton.dataset.typeFilter === "bookmarks") {
          if (activeType === "bookmarks") {
            activeType = previousType;
          } else {
            previousType = activeType;
            activeType = "bookmarks";
          }
        } else {
          activeType = typeButton.dataset.typeFilter;
          previousType = activeType;
        }
        currentPage = 1;
        document.querySelectorAll("[data-type-filter]").forEach(function (button) {
          button.classList.toggle("is-active", button === typeButton);
          button.setAttribute(
            "aria-pressed",
            String(button.dataset.typeFilter === activeType)
          );
        });

        typeButton.classList.toggle("is-active", activeType === typeButton.dataset.typeFilter);
        if (typeSelect && activeType !== "bookmarks") typeSelect.value = activeType;
        if (activeType === "bookmarks") history.replaceState(null, "", "#bookmarks");
        else if (location.hash === "#bookmarks") history.replaceState(null, "", location.pathname);
        updateCards();
      }

      const newButton = event.target.closest("[data-new-filter]");
      if (newButton) {
        showNew = !showNew;
        currentPage = 1;
        newButton.classList.toggle("is-active", showNew);
        newButton.setAttribute("aria-pressed", String(showNew));
        updateCards();
      }

      const topicButton = event.target.closest("[data-topic-filter]");
      if (topicButton) {
        activeTopic = topicButton.dataset.topicFilter;
        currentPage = 1;
        document.querySelectorAll("[data-topic-filter]").forEach(function (button) {
          button.classList.toggle("is-active", button.dataset.topicFilter === activeTopic);
        });
        if (topicSelect) topicSelect.value = activeTopic;
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

      const copyButton = event.target.closest("[data-copy-link]");
      if (copyButton) {
        const card = copyButton.closest("[data-news-card]");
        copyLink(card.dataset.url).then(function (copied) {
          setButtonFeedback(copyButton, copied ? "Copied" : "Copy failed");
          if (copied) {
            window.setTimeout(function () {
              copyButton.closest("details").open = false;
            }, 800);
          }
        });
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
        scrollToGrid(grid);
      }
      if (event.target.closest("[data-page-next]")) {
        currentPage += 1;
        renderArchive();
        scrollToGrid(grid);
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        document.querySelectorAll(".share-control[open]").forEach(function (menu) {
          menu.open = false;
        });
        document.querySelectorAll(".browser-settings[open]").forEach(function (settings) {
          settings.open = false;
        });
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

    if (typeSelect) {
      typeSelect.value = activeType === "bookmarks" ? "all" : activeType;
      typeSelect.addEventListener("change", function () {
        activeType = typeSelect.value;
        previousType = activeType;
        currentPage = 1;
        document.querySelectorAll("[data-type-filter]").forEach(function (button) {
          button.classList.remove("is-active");
          button.setAttribute("aria-pressed", "false");
        });
        if (location.hash === "#bookmarks") history.replaceState(null, "", location.pathname);
        updateCards();
      });
    }

    if (topicSelect) {
      topicSelect.value = activeTopic;
      topicSelect.addEventListener("change", function () {
        activeTopic = topicSelect.value;
        currentPage = 1;
        updateCards();
      });
    }

    if (aiSubtopicSelect) {
      aiSubtopicSelect.value = activeAISubtopic;
      aiSubtopicSelect.addEventListener("change", function () {
        activeAISubtopic = aiSubtopicSelect.value;
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

    const densityButtons = Array.from(
      document.querySelectorAll("[data-density-option]")
    );
    const setDensity = function (density) {
      const selected = density === "compact" ? "compact" : "comfortable";
      storage.set("newsDensity", selected);
      grid.classList.toggle("is-compact", selected === "compact");
      densityButtons.forEach(function (button) {
        const active = button.dataset.densityOption === selected;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
    };
    if (densityButtons.length) {
      setDensity(storage.get("newsDensity", "comfortable"));
      densityButtons.forEach(function (button) {
        button.addEventListener("click", function () {
          setDensity(button.dataset.densityOption);
        });
      });
    }

    document.querySelectorAll("[data-type-filter]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.typeFilter === activeType);
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.typeFilter === activeType)
      );
    });
    document.querySelectorAll("[data-topic-filter]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.topicFilter === activeTopic);
    });
    updateNewCount(
      cards.map(function (card) {
        return {
          contentType: card.dataset.contentType,
          date: card.dataset.date
        };
      })
    );
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
          populateAISubtopics(items);
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

  const releaseRadar = document.querySelector("[data-release-radar]");
  if (releaseRadar) {
    const releaseItems = Array.from(
      releaseRadar.querySelectorAll("[data-release-item]")
    );
    const releaseMore = releaseRadar.querySelector("[data-release-more]");
    let releaseFilter = "all";
    let releaseLimit = 8;

    const updateReleases = function () {
      const matching = releaseItems.filter(function (item) {
        return releaseFilter === "all" || item.dataset.releaseType === releaseFilter;
      });
      releaseItems.forEach(function (item) {
        const index = matching.indexOf(item);
        item.hidden = index === -1 || index >= releaseLimit;
      });
      if (releaseMore) {
        const remaining = Math.max(0, matching.length - releaseLimit);
        releaseMore.hidden = matching.length <= releaseLimit;
        releaseMore.textContent = `Show ${Math.min(8, remaining)} more releases`;
      }
    };

    releaseRadar.addEventListener("click", function (event) {
      const filter = event.target.closest("[data-release-filter]");
      if (filter) {
        releaseFilter = filter.dataset.releaseFilter;
        releaseLimit = 8;
        releaseRadar.querySelectorAll("[data-release-filter]").forEach(function (button) {
          const active = button === filter;
          button.classList.toggle("is-active", active);
          button.setAttribute("aria-pressed", String(active));
        });
        updateReleases();
      }
      if (event.target.closest("[data-release-more]")) {
        releaseLimit += 8;
        updateReleases();
      }
    });
    updateReleases();
  }

  const pulseItems = Array.from(document.querySelectorAll("[data-pulse-item]"));
  if (pulseItems.length) {
    let pulsePlatform = "all";
    let pulseQuery = "";
    const updatePulse = function () {
      let visible = 0;
      pulseItems.forEach(function (item) {
        const show =
          (pulsePlatform === "all" || item.dataset.pulsePlatform === pulsePlatform)
          && (!pulseQuery || item.textContent.toLowerCase().includes(pulseQuery));
        item.hidden = !show;
        if (show) visible += 1;
      });
      document.querySelectorAll("[data-pulse-group]").forEach(function (group) {
        group.hidden = !Array.from(group.querySelectorAll("[data-pulse-item]"))
          .some(function (item) { return !item.hidden; });
      });
      const count = document.querySelector("[data-pulse-count]");
      if (count) count.textContent = `${visible} ${visible === 1 ? "post" : "posts"}`;
      const empty = document.querySelector("[data-pulse-empty]");
      if (empty) empty.hidden = visible !== 0;
    };

    const search = document.querySelector("[data-pulse-search]");
    if (search) {
      search.addEventListener("input", function () {
        pulseQuery = search.value.trim().toLowerCase();
        updatePulse();
      });
    }
    document.querySelectorAll("[data-pulse-platform]").forEach(function (button) {
      button.addEventListener("click", function () {
        pulsePlatform = button.dataset.pulsePlatform;
        document.querySelectorAll("[data-pulse-platform]").forEach(function (candidate) {
          const active = candidate === button;
          candidate.classList.toggle("is-active", active);
          candidate.setAttribute("aria-pressed", String(active));
        });
        updatePulse();
      });
    });
  }
})();
