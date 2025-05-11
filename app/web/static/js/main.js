/**
 * 業務データ統合ハブ - Main JavaScript
 * ドキュメントのアップロード、検索、ユーザーインターフェースを制御します
 */

// DOM ready event handler
document.addEventListener('DOMContentLoaded', function() {
    // Initialize UI components
    initializeUI();

    // Initialize upload functionality if on upload page
    const uploadArea = document.getElementById('upload-area');
    if (uploadArea) {
        initializeUpload();
    }

    // Initialize search functionality if on search page
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        initializeSearch();
    }

    // Initialize document view if on document page
    const documentView = document.getElementById('document-view');
    if (documentView) {
        initializeDocumentView();
    }
});

/**
 * Initialize UI components
 */
function initializeUI() {
    // Mobile navigation toggle
    const navToggle = document.getElementById('nav-toggle');
    if (navToggle) {
        navToggle.addEventListener('click', function() {
            const navMenu = document.getElementById('nav-menu');
            navMenu.classList.toggle('active');
        });
    }

    // Show/hide advanced search options
    const advancedSearchToggle = document.getElementById('advanced-search-toggle');
    if (advancedSearchToggle) {
        advancedSearchToggle.addEventListener('click', function() {
            const advancedOptions = document.getElementById('advanced-search-options');
            advancedOptions.classList.toggle('hidden');
            this.textContent = advancedOptions.classList.contains('hidden')
                ? '詳細検索を表示'
                : '詳細検索を隠す';
        });
    }

    // Initialize date pickers
    const datePickers = document.querySelectorAll('.date-picker');
    datePickers.forEach(function(picker) {
        picker.type = 'date';
    });
}

/**
 * Initialize file upload functionality
 */
function initializeUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const uploadForm = document.getElementById('upload-form');

    // Handle drag and drop events
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('active');
    });

    uploadArea.addEventListener('dragleave', function() {
        uploadArea.classList.remove('active');
    });

    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('active');
        handleFiles(e.dataTransfer.files);
    });

    // Handle click to upload
    uploadArea.addEventListener('click', function() {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    // Handle file selection
    function handleFiles(files) {
        updateFileList(files);
    }

    // Update file list display
    function updateFileList(files) {
        fileList.innerHTML = '';

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';

            const fileName = document.createElement('div');
            fileName.className = 'file-name';
            fileName.textContent = file.name;

            const fileSize = document.createElement('div');
            fileSize.className = 'file-size';
            fileSize.textContent = formatFileSize(file.size);

            const fileRemove = document.createElement('div');
            fileRemove.className = 'file-remove';
            fileRemove.textContent = '✕';
            fileRemove.addEventListener('click', function() {
                fileItem.remove();
                // We can't actually remove from FileList, but we can clear and recreate fileInput
                // if we need to implement this functionality
            });

            fileItem.appendChild(fileName);
            fileItem.appendChild(fileSize);
            fileItem.appendChild(fileRemove);
            fileList.appendChild(fileItem);
        }
    }

    // Handle form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(uploadForm);
            const uploadStatus = document.getElementById('upload-status');

            uploadStatus.textContent = 'アップロード中...';
            uploadStatus.className = '';

            fetch('/api/documents/', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('アップロードに失敗しました');
                }
                return response.json();
            })
            .then(data => {
                uploadStatus.textContent = 'アップロード完了！';
                uploadStatus.className = 'success';

                // Clear form and file list
                uploadForm.reset();
                fileList.innerHTML = '';

                // Redirect to document page
                setTimeout(() => {
                    window.location.href = `/documents/${data.id}`;
                }, 1000);
            })
            .catch(error => {
                uploadStatus.textContent = error.message;
                uploadStatus.className = 'error';
            });
        });
    }
}

/**
 * Initialize search functionality
 */
function initializeSearch() {
    const searchForm = document.getElementById('search-form');
    const resultsContainer = document.getElementById('search-results');

    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // Get form data
        const formData = new FormData(searchForm);
        const searchData = {};

        for (const [key, value] of formData.entries()) {
            if (value) {
                searchData[key] = value;
            }
        }

        // Show loading indicator
        resultsContainer.innerHTML = '<div class="loading">検索中...</div>';

        // Send search request
        fetch('/api/search/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(searchData)
        })
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data);
        })
        .catch(error => {
            resultsContainer.innerHTML = `<div class="error">検索エラー: ${error.message}</div>`;
        });
    });

    // Display search results
    function displaySearchResults(data) {
        if (!data.results || data.results.length === 0) {
            resultsContainer.innerHTML = '<div class="no-results">検索結果はありません</div>';
            return;
        }

        const resultsHTML = `
            <div class="search-summary">
                ${data.total} 件中 ${(data.page - 1) * data.per_page + 1} - ${Math.min(data.page * data.per_page, data.total)} 件を表示
                (${data.execution_time.toFixed(3)} 秒)
            </div>
            <div class="results-list">
                ${data.results.map(result => `
                    <div class="result-item">
                        <div class="result-title">
                            <a href="/documents/${result.id}">${result.title}</a>
                        </div>
                        ${result.snippet ? `<div class="result-snippet">${result.snippet}</div>` : ''}
                        <div class="result-meta">
                            <span class="result-type">${result.doc_type || '未分類'}</span>
                            <span class="result-date">${new Date(result.created_at).toLocaleDateString('ja-JP')}</span>
                            ${result.department ? `<span class="result-department">${result.department}</span>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
            ${generatePagination(data.page, data.total_pages)}
        `;

        resultsContainer.innerHTML = resultsHTML;

        // Add event listeners to pagination links
        const paginationLinks = resultsContainer.querySelectorAll('.pagination a');
        paginationLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const page = parseInt(this.getAttribute('data-page'));

                // Update page input and submit form
                document.getElementById('page').value = page;
                searchForm.dispatchEvent(new Event('submit'));

                // Scroll to top of results
                resultsContainer.scrollIntoView({ behavior: 'smooth' });
            });
        });
    }

    // Generate pagination HTML
    function generatePagination(currentPage, totalPages) {
        if (totalPages <= 1) {
            return '';
        }

        let paginationHTML = '<div class="pagination">';

        // Previous page
        if (currentPage > 1) {
            paginationHTML += `<a href="#" data-page="${currentPage - 1}">前へ</a>`;
        } else {
            paginationHTML += `<span>前へ</span>`;
        }

        // Page numbers
        const maxPages = 5;
        let startPage = Math.max(1, currentPage - Math.floor(maxPages / 2));
        let endPage = Math.min(totalPages, startPage + maxPages - 1);

        if (endPage - startPage + 1 < maxPages) {
            startPage = Math.max(1, endPage - maxPages + 1);
        }

        for (let i = startPage; i <= endPage; i++) {
            if (i === currentPage) {
                paginationHTML += `<span>${i}</span>`;
            } else {
                paginationHTML += `<a href="#" data-page="${i}">${i}</a>`;
            }
        }

        // Next page
        if (currentPage < totalPages) {
            paginationHTML += `<a href="#" data-page="${currentPage + 1}">次へ</a>`;
        } else {
            paginationHTML += `<span>次へ</span>`;
        }

        paginationHTML += '</div>';
        return paginationHTML;
    }

    // Load document types for filter
    loadDocumentTypes();
}

/**
 * Initialize document view functionality
 */
function initializeDocumentView() {
    const documentId = document.getElementById('document-view').getAttribute('data-id');

    // Load document metadata
    fetch(`/api/documents/${documentId}`)
        .then(response => response.json())
        .then(data => {
            displayDocumentMetadata(data);
        })
        .catch(error => {
            console.error('Error loading document:', error);
        });

    // Handle classification form submission
    const classificationForm = document.getElementById('classification-form');
    if (classificationForm) {
        classificationForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(classificationForm);
            const updateData = {};

            for (const [key, value] of formData.entries()) {
                updateData[key] = value;
            }

            // Send update request
            fetch(`/api/documents/${documentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            })
            .then(response => response.json())
            .then(data => {
                // Show success message
                const updateStatus = document.getElementById('update-status');
                updateStatus.textContent = '更新しました';
                updateStatus.className = 'success';

                // Update displayed metadata
                displayDocumentMetadata(data);

                // Clear status after a moment
                setTimeout(() => {
                    updateStatus.textContent = '';
                    updateStatus.className = '';
                }, 3000);
            })
            .catch(error => {
                // Show error message
                const updateStatus = document.getElementById('update-status');
                updateStatus.textContent = `更新エラー: ${error.message}`;
                updateStatus.className = 'error';
            });
        });
    }
}

/**
 * Display document metadata
 */
function displayDocumentMetadata(data) {
    // Update document title
    const titleElement = document.getElementById('document-title');
    if (titleElement) {
        titleElement.textContent = data.title;
    }

    // Update document type
    const typeElement = document.getElementById('document-type');
    if (typeElement) {
        typeElement.textContent = data.doc_type || '未分類';
    }

    // Update created date
    const dateElement = document.getElementById('document-date');
    if (dateElement) {
        dateElement.textContent = new Date(data.created_at).toLocaleDateString('ja-JP');
    }

    // Update department
    const departmentElement = document.getElementById('document-department');
    if (departmentElement) {
        departmentElement.textContent = data.department || '-';
    }

    // Update fields
    const fieldsContainer = document.getElementById('document-fields');
    if (fieldsContainer && data.fields) {
        fieldsContainer.innerHTML = '';

        for (const field of data.fields) {
            const fieldItem = document.createElement('div');
            fieldItem.className = 'field-item';

            const fieldName = document.createElement('div');
            fieldName.className = 'field-name';
            fieldName.textContent = field.field_name;

            const fieldValue = document.createElement('div');
            fieldValue.className = 'field-value';
            fieldValue.textContent = field.field_value;

            fieldItem.appendChild(fieldName);
            fieldItem.appendChild(fieldValue);
            fieldsContainer.appendChild(fieldItem);
        }
    }

    // Update classification form if exists
    const docTypeSelect = document.getElementById('doc_type');
    if (docTypeSelect) {
        docTypeSelect.value = data.doc_type || '';
    }
}

/**
 * Load document types for filter
 */
function loadDocumentTypes() {
    const docTypeSelect = document.getElementById('doc_type');
    if (!docTypeSelect) return;

    fetch('/api/search/document-types')
        .then(response => response.json())
        .then(data => {
            if (data.types && data.types.length > 0) {
                let options = '<option value="">すべての文書タイプ</option>';

                data.types.forEach(type => {
                    options += `<option value="${type}">${type}</option>`;
                });

                docTypeSelect.innerHTML = options;
            }
        })
        .catch(error => {
            console.error('Error loading document types:', error);
        });
}

/**
 * Format file size in bytes to human-readable string
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));

    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + units[i];
}