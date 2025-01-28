document.addEventListener('DOMContentLoaded', function () {
    const postsContainer = document.getElementById('posts-container');
    if (!postsContainer) return;

    let page = 1;
    let isLoading = false;
    let loadedPostUrls = new Set();  // Track loaded URLs to prevent duplicates

    function loadMorePosts() {
        if (isLoading) return;
        isLoading = true;  // Prevent multiple requests

        fetch(`/rssfeeds/api?page=${page}`)
            .then(response => response.json())
            .then(data => {
                if (!data.posts || data.posts.length === 0) return;

                data.posts.forEach(post => {
                    if (loadedPostUrls.has(post.url)) return;
                    loadedPostUrls.add(post.url); // ✅ Prevent duplicate inserts

                    const sourceBaseUrl = post.base_url.replace(/https?:\/\//, '');

                    const card = `
                        <div class="col-md-4">
                            <div class="card mb-3 shadow-sm">
                                <img src="${post.image_url || '/static/assets/img/default-placeholder.png'}"
                                     class="card-img-top"
                                     alt="${post.title}"
                                     onerror="this.onerror=null; this.src='/static/assets/img/default-placeholder.png';">
                                <div class="card-body">
                                    <div class="d-flex align-items-center mb-2">
                                        <img src="${post.favicon_url || '/static/assets/img/default-favicon.png'}" 
                                             alt="Favicon" 
                                             width="16" 
                                             height="16" 
                                             class="me-2">
                                        <small class="text-muted">${sourceBaseUrl}</small>
                                    </div>
                                    <h5 class="card-title">
                                        <a href="${post.url}" target="_blank" class="post-link" data-url="${post.url}">
                                            ${post.title}
                                        </a>
                                    </h5>
                                    <p class="card-text">${post.content}</p>
                                    <p class="card-text">
                                        <small class="text-muted">Posted on ${post.post_date}</small>
                                    </p>
                                </div>
                            </div>
                        </div>`;
                    postsContainer.insertAdjacentHTML('beforeend', card);
                });

                if (data.has_more) {
                    page++;
                    isLoading = false; // ✅ Allow the next fetch only after response
                } else {
                    window.removeEventListener('scroll', onScroll); // ✅ Stop unnecessary requests
                }
            })
            .catch(error => {
                console.error('Error fetching posts:', error);
            })
            .finally(() => {
                isLoading = false; // ✅ Ensure state is reset after fetch
            });
    }

    function onScroll() {
        if (isLoading) return; // ✅ Prevent spamming API calls
        const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
        if (scrollTop + clientHeight >= scrollHeight - 50) {
            loadMorePosts();
        }
    }

    window.addEventListener('scroll', onScroll);
    loadMorePosts(); // ✅ Load the first batch
});