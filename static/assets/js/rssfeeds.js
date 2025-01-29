document.addEventListener('DOMContentLoaded', function () {
    const postsContainer = document.getElementById('posts-container');
    if (!postsContainer) return;

    let page = 1;
    let isLoading = false;
    let loadedPages = new Set(); // Prevent duplicate API calls

    function loadMorePosts() {
        if (isLoading || loadedPages.has(page)) return; // Skip duplicate page requests
        isLoading = true;
        loadedPages.add(page); // Mark this page as loaded

        console.log(`Fetching Page: ${page}`); // Debugging

        fetch(`/rssfeeds/api?page=${page}`)
            .then(response => response.json())
            .then(data => {
                console.log(`API Response (Page ${page}):`, data.posts.map(p => p.id)); // Debugging

                if (!data.posts || data.posts.length === 0) {
                    console.log("No more posts to load.");
                    window.removeEventListener('scroll', onScroll); // Stop scrolling event
                    return;
                }
                data.posts.forEach(post => {
                    const sourceBaseUrl = post.base_url.replace(/https?:\/\//, '');

                    const card = `
                        <div class="fixed masonry-item">
                            <div class="card mb-3 shadow-sm">
                                <img class="post_image" src="${post.image_url || '/static/assets/img/default-placeholder.png'}"
                                     class="card-img-top"
                                     alt="${post.title}"
                                     onerror="this.onerror=null; this.src='/static/assets/img/default-placeholder.png';">
                                <div class="card-body">
                                    <!-- Favicon & Base URL -->
                                    <div class="d-flex align-items-center mb-2">
                                        <img src="${post.favicon_url || '/static/assets/img/favicon.png'}" 
                                             alt="Favicon" 
                                             width="16" 
                                             height="16" 
                                             class="me-2">
                                        <small class="text-muted">${sourceBaseUrl}</small>
                                    </div>

                                    <!--  Moved "Posted on" section BELOW source -->
                                    <div class="mb-2">
                                        <small class="text-muted">Posted on ${post.post_date}</small>
                                    </div>

                                    <!--  Post Title -->
                                    <h5 class="card-title">
                                        <a href="${post.url}" target="_blank" class="post-link" data-url="${post.url}">
                                            ${post.title}
                                        </a>
                                    </h5>

                                    <p class="card-text">${post.content}</p>
                                </div>
                            </div>
                        </div>`;
                    postsContainer.insertAdjacentHTML('beforeend', card);
                });

                if (data.has_more) {
                    page++; 
                } else {
                    console.log("🛑 No more pages available.");
                    window.removeEventListener('scroll', onScroll);
                }
            })
            .catch(error => {
                console.error('❌ Error fetching posts:', error);
            })
            .finally(() => {
                isLoading = false;
            });
    }

    function onScroll() {
        if (isLoading) return;
        const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
        if (scrollTop + clientHeight >= scrollHeight - 50) {
            loadMorePosts();
        }
    }

        // Log Read Actions
    postsContainer.addEventListener('click', function (event) {
        const postLink = event.target.closest('a');
        if (postLink) {
            const rssFeedContentUrl = postLink.getAttribute('data-url'); // Use the data-url attribute

            if (rssFeedContentUrl) {
                fetch('/rssfeeds/log', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ rss_feed_content_url: rssFeedContentUrl }),
                })
                .then(response => response.json())
                .then(data => {
                    console.log('✅ Read log created:', data);
                })
                .catch(error => {
                    console.error('❌ Error logging read:', error);
                });
            }
        }
    });

    


    window.addEventListener("load", () => {
        const masonryGrid = document.querySelector("#posts-container");
    
        if (!masonryGrid) return;
    
        // Masonry példány létrehozása
        const masonryInstance = new Masonry(masonryGrid, {
            itemSelector: '.masonry-item',
            columnWidth: '.fixed',
            percentPosition: true
        });
    
        console.log("Masonry példány:", masonryInstance);
    
        // FIGYELJÜK, ha ÚJ elemek kerülnek be
        const observer = new MutationObserver(() => {
            console.log("Új elemek észlelve, Masonry újrarenderelése...");
            masonryInstance.reloadItems();
            masonryInstance.layout();
        });
    
        observer.observe(masonryGrid, { childList: true, subtree: true });
    });
    



    window.addEventListener('scroll', onScroll);
    loadMorePosts();
});