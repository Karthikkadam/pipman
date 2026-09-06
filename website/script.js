/**
 * PipMan (v2.4) - Interactive Website Simulator & Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
    initSimulator();
    initFAQ();
    initSmoothScroll();
});

// Initial Simulator Mock Data
let packagesData = [
    { name: 'matplotlib', version: '3.8.2', latest: '3.8.2', sizeMb: 87.5, sizeStr: '87.5 MB', date: '2025-11-15' },
    { name: 'pandas', version: '2.1.3', latest: '2.2.0', sizeMb: 74.2, sizeStr: '74.2 MB', date: '2025-11-10' },
    { name: 'numpy', version: '1.26.2', latest: '1.26.2', sizeMb: 65.1, sizeStr: '65.1 MB', date: '2025-11-12' },
    { name: 'tensorflow', version: '2.15.0', latest: '2.16.1', sizeMb: 610.9, sizeStr: '610.9 MB', date: '2025-10-25' },
    { name: 'scipy', version: '1.11.4', latest: '1.11.4', sizeMb: 52.3, sizeStr: '52.3 MB', date: '2025-11-14' },
    { name: 'ipython', version: '8.17.2', latest: '8.18.0', sizeMb: 28.6, sizeStr: '28.6 MB', date: '2025-11-11' },
    { name: 'requests', version: '2.31.0', latest: '2.31.0', sizeMb: 4.8, sizeStr: '4.8 MB', date: '2025-11-05' }
];

let currentPackages = [...packagesData];
let currentSortKey = 'name';
let currentSortDesc = false;
let isTerminalBusy = false;

function initSimulator() {
    const tableBody = document.getElementById('sim-table-rows');
    const searchInput = document.getElementById('sim-search-input');
    const packageCount = document.getElementById('sim-package-count');
    const refreshBtn = document.getElementById('sim-refresh-btn');
    const secRefreshBtn = document.getElementById('sim-sec-refresh-btn');
    const termBody = document.getElementById('sim-terminal-content');
    const logToggle = document.getElementById('sim-log-toggle');
    const logClear = document.getElementById('sim-log-clear');
    const logContainer = document.getElementById('sim-log-container');

    // Render Initial Table
    renderTable();

    // 1. Search Filter
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim().toLowerCase();
        if (!query) {
            currentPackages = [...packagesData];
        } else {
            currentPackages = packagesData.filter(p => p.name.toLowerCase().includes(query));
        }
        sortData(currentSortKey, currentSortDesc);
        renderTable();
    });

    // 2. Sort Headers
    document.querySelectorAll('.sim-col[data-sort]').forEach(header => {
        header.addEventListener('click', () => {
            const key = header.getAttribute('data-sort');
            if (currentSortKey === key) {
                currentSortDesc = !currentSortDesc;
            } else {
                currentSortKey = key;
                currentSortDesc = false;
            }
            sortData(currentSortKey, currentSortDesc);
            renderTable();
        });
    });

    // 3. Refresh Buttons
    const triggerRefresh = () => {
        logToTerminal(`Scanning packages in environment...`, 'info');
        setTimeout(() => {
            currentPackages = [...packagesData];
            searchInput.value = '';
            sortData('name', false);
            renderTable();
            logToTerminal(`Loaded ${packagesData.length} installed packages.`, 'success');
            logPrompt('Ready for commands.');
        }, 500);
    };

    refreshBtn.addEventListener('click', triggerRefresh);
    secRefreshBtn.addEventListener('click', triggerRefresh);

    // 4. Terminal Controls
    logClear.addEventListener('click', () => {
        termBody.innerHTML = '';
        logPrompt('Ready for commands.');
    });

    logToggle.addEventListener('click', () => {
        if (termBody.style.display === 'none') {
            termBody.style.display = 'flex';
            logToggle.textContent = '—';
        } else {
            termBody.style.display = 'none';
            logToggle.textContent = '□';
        }
    });
}

function sortData(key, desc) {
    currentPackages.sort((a, b) => {
        let valA = a[key] || a.sizeMb;
        let valB = b[key] || b.sizeMb;

        if (key === 'size') {
            valA = a.sizeMb;
            valB = b.sizeMb;
        } else if (key === 'name' || key === 'date' || key === 'version' || key === 'latest') {
            valA = a[key].toLowerCase();
            valB = b[key].toLowerCase();
        }

        if (valA < valB) return desc ? 1 : -1;
        if (valA > valB) return desc ? -1 : 1;
        return 0;
    });
}

function renderTable() {
    const tableBody = document.getElementById('sim-table-rows');
    const packageCount = document.getElementById('sim-package-count');

    packageCount.textContent = `INSTALLED PACKAGES (${currentPackages.length})`;
    tableBody.innerHTML = '';

    if (currentPackages.length === 0) {
        tableBody.innerHTML = `
            <div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">
                No matching packages found.
            </div>
        `;
        return;
    }

    currentPackages.forEach((pkg, index) => {
        const row = document.createElement('div');
        row.className = 'sim-row';

        const isUpdateAvail = pkg.latest !== pkg.version;
        const latestClass = isUpdateAvail ? 'col-latest update-avail' : 'col-latest';

        row.innerHTML = `
            <div class="sim-col col-name">${index + 1}.  ${pkg.name}</div>
            <div class="sim-col col-ver">${pkg.version}</div>
            <div class="sim-col ${latestClass}">${pkg.latest}</div>
            <div class="sim-col col-size">${pkg.sizeStr}</div>
            <div class="sim-col col-date">${pkg.date}</div>
            <div class="sim-col col-actions">
                <div class="sim-action-btns">
                    <button class="sim-pill-btn btn-sim-update" data-action="update" data-pkg="${pkg.name}">Update</button>
                    <button class="sim-pill-btn btn-sim-uninstall" data-action="uninstall" data-pkg="${pkg.name}">Uninstall</button>
                </div>
            </div>
        `;

        // Bind Update Button
        row.querySelector('[data-action="update"]').addEventListener('click', (e) => {
            e.stopPropagation();
            simulateUpdate(pkg.name);
        });

        // Bind Uninstall Button
        row.querySelector('[data-action="uninstall"]').addEventListener('click', (e) => {
            e.stopPropagation();
            simulateUninstall(pkg.name);
        });

        tableBody.appendChild(row);
    });
}

function simulateUpdate(pkgName) {
    if (isTerminalBusy) return;
    isTerminalBusy = true;

    logPrompt(`pip install --upgrade ${pkgName}`);
    logToTerminal(`Requirement already satisfied: ${pkgName}`, 'output');
    logToTerminal(`Collecting ${pkgName} (latest version)...`, 'output');
    logToTerminal(`Downloading wheel packages [100%]...`, 'output');
    
    setTimeout(() => {
        // Upgrade mock data
        const pkg = packagesData.find(p => p.name === pkgName);
        if (pkg) {
            pkg.version = pkg.latest;
        }
        renderTable();
        logToTerminal(`Successfully installed ${pkgName}-${pkg ? pkg.version : 'latest'}`, 'success');
        logPrompt('Ready for commands.');
        isTerminalBusy = false;
    }, 1200);
}

function simulateUninstall(pkgName) {
    if (isTerminalBusy) return;

    if (!confirm(`[PipMan Simulator]\nAre you sure you want to uninstall '${pkgName}'?`)) {
        return;
    }

    isTerminalBusy = true;
    logPrompt(`pip uninstall -y ${pkgName}`);
    logToTerminal(`Found existing installation: ${pkgName}`, 'output');
    logToTerminal(`Uninstalling ${pkgName}...`, 'output');

    setTimeout(() => {
        packagesData = packagesData.filter(p => p.name !== pkgName);
        currentPackages = currentPackages.filter(p => p.name !== pkgName);
        renderTable();
        logToTerminal(`Successfully uninstalled ${pkgName}`, 'success');
        logPrompt('Ready for commands.');
        isTerminalBusy = false;
    }, 1000);
}

function logPrompt(cmdText) {
    const termBody = document.getElementById('sim-terminal-content');
    const line = document.createElement('div');
    line.className = 'term-line';
    line.innerHTML = `<span class="term-prompt">pipman ~$ </span><span class="term-cmd">${cmdText}</span>`;
    termBody.appendChild(line);
    termBody.scrollTop = termBody.scrollHeight;
}

function logToTerminal(text, type = 'output') {
    const termBody = document.getElementById('sim-terminal-content');
    const line = document.createElement('div');
    line.className = `term-line term-${type}`;
    line.textContent = text;
    termBody.appendChild(line);
    termBody.scrollTop = termBody.scrollHeight;
}

// FAQ Accordion
function initFAQ() {
    const faqItems = document.querySelectorAll('.faq-item');

    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        const answer = item.querySelector('.faq-answer');

        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');

            // Close all
            faqItems.forEach(i => {
                i.classList.remove('active');
                i.querySelector('.faq-answer').style.maxHeight = null;
            });

            // Toggle current
            if (!isActive) {
                item.classList.add('active');
                answer.style.maxHeight = answer.scrollHeight + 'px';
            }
        });
    });
}

// Smooth Scrolling
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
}
