/**
 * TIF下载工具 - 前端交互逻辑
 */

// ============ 全局变量 ============
let map;
let drawnItems;
let drawControl;
let currentBounds = null;
let currentPolygon = null;
let boundaryLayer = null;
let mapLayers = {}; // Store layer objects by ID

// ============ 工具函数 ============
/**
 * 从 GeoJSON 中提取多边形坐标
 * 支持 Polygon 和 MultiPolygon，返回最大的多边形
 */
function extractPolygonFromGeoJSON(geojson) {
    if (!geojson) return null;
    
    let coordinates = null;
    
    // 处理 FeatureCollection
    if (geojson.type === 'FeatureCollection' && geojson.features && geojson.features.length > 0) {
        const geometry = geojson.features[0].geometry;
        if (geometry.type === 'Polygon') {
            coordinates = geometry.coordinates[0]; // 外环
        } else if (geometry.type === 'MultiPolygon') {
            // 找最大的多边形（通常是主要边界）
            let maxLen = 0;
            for (const poly of geometry.coordinates) {
                if (poly[0].length > maxLen) {
                    maxLen = poly[0].length;
                    coordinates = poly[0];
                }
            }
        }
    } else if (geojson.type === 'Feature') {
        const geometry = geojson.geometry;
        if (geometry.type === 'Polygon') {
            coordinates = geometry.coordinates[0];
        } else if (geometry.type === 'MultiPolygon') {
            let maxLen = 0;
            for (const poly of geometry.coordinates) {
                if (poly[0].length > maxLen) {
                    maxLen = poly[0].length;
                    coordinates = poly[0];
                }
            }
        }
    }
    
    if (!coordinates) return null;
    
    // GeoJSON 坐标是 [lng, lat]，转换为 {lat, lng} 格式
    return coordinates.map(coord => ({
        lat: coord[1],
        lng: coord[0]
    }));
}

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', function() {
    initMap(); // This will now be async-like internally
    initDrawControls();
    initEventListeners();
    initSidebarToggle();
    loadProvinces();
});

// ============ 地图初始化 ============
async function initMap() {
    // 创建地图，默认中心在中国
    map = L.map('map', { zoomControl: false }).setView([35.8617, 104.1954], 5);
    
    // 添加缩放控件到右上角
    L.control.zoom({
        position: 'topright'
    }).addTo(map);
    
    // 绘制图层
    drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    
    // 获取并加载所有图源
    try {
        const response = await fetch('/api/sources');
        const sources = await response.json();
        
        const baseMaps = {};
        let firstLayer = null;
        
        for (const [key, config] of Object.entries(sources)) {
            const layer = L.tileLayer(config.url, {
                attribution: config.attribution,
                maxZoom: config.max_zoom,
                subdomains: config.subdomains || []
            });
            
            mapLayers[key] = layer;
            baseMaps[config.name] = layer;
            
            if (!firstLayer) firstLayer = layer;
        }
        
        // 默认添加第一个图源 (通常是OSM或列表中第一个)
        // 优先使用 OSM 或 Tianditu Vector
        if (mapLayers['osm']) {
            mapLayers['osm'].addTo(map);
        } else if (firstLayer) {
            firstLayer.addTo(map);
        }
        
        // 添加图层控制
        L.control.layers(baseMaps).addTo(map);
        
        // 绑定下拉框联动
        syncDropdownWithMap();
        
    } catch (error) {
        console.error('Failed to load tile sources:', error);
        // Fallback to OSM if API fails
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);
    }
}

function syncDropdownWithMap() {
    const sourceSelect = document.getElementById('source-select');
    
    // 当下拉框改变时，切换地图图层
    sourceSelect.addEventListener('change', function(e) {
        const selectedKey = e.target.value;
        if (mapLayers[selectedKey]) {
            // 移除所有基础图层
            for (const key in mapLayers) {
                if (map.hasLayer(mapLayers[key])) {
                    map.removeLayer(mapLayers[key]);
                }
            }
            // 添加选中的图层
            mapLayers[selectedKey].addTo(map);
        }
    });
    
    // 当地图图层通过控件改变时，更新下拉框 (可选，但为了双向同步最好加上)
    map.on('baselayerchange', function(e) {
        // Find key by name
        for (const [key, layer] of Object.entries(mapLayers)) {
            if (layer === e.layer) {
                sourceSelect.value = key;
                break;
            }
        }
    });
}

// ============ 绘制控件初始化 ============
function initDrawControls() {
    drawControl = new L.Control.Draw({
        position: 'topright',
        draw: {
            polyline: false,
            circle: false,
            circlemarker: false,
            marker: false,
            polygon: {
                allowIntersection: false,
                shapeOptions: {
                    color: '#0052cc',
                    fillColor: '#0052cc',
                    fillOpacity: 0.2,
                    weight: 2
                }
            },
            rectangle: {
                shapeOptions: {
                    color: '#0052cc',
                    fillColor: '#0052cc',
                    fillOpacity: 0.2,
                    weight: 2
                }
            }
        },
        edit: {
            featureGroup: drawnItems,
            remove: true
        }
    });
    
    map.addControl(drawControl);
    
    // 绘制完成事件
    map.on(L.Draw.Event.CREATED, function(e) {
        // 清除之前的绘制
        drawnItems.clearLayers();
        if (boundaryLayer) {
            map.removeLayer(boundaryLayer);
            boundaryLayer = null;
        }
        
        // 添加新绘制
        drawnItems.addLayer(e.layer);
        
        // 获取边界
        if (e.layerType === 'rectangle') {
            const bounds = e.layer.getBounds();
            currentBounds = {
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest()
            };
            currentPolygon = null;
        } else if (e.layerType === 'polygon') {
            const latlngs = e.layer.getLatLngs()[0];
            currentPolygon = latlngs.map(ll => ({ lat: ll.lat, lng: ll.lng }));
            // 计算边界框
            const bounds = e.layer.getBounds();
            currentBounds = {
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest()
            };
        }
        
        updateSelectionInfo();
        estimateDownload();
        updateVectorButtons();
    });
    
    // 删除事件
    map.on(L.Draw.Event.DELETED, function(e) {
        currentBounds = null;
        currentPolygon = null;
        updateSelectionInfo();
        document.getElementById('download-btn').disabled = true;
        updateVectorButtons();
    });
}

// ============ 侧边栏切换 ============
function initSidebarToggle() {
    const sidebar = document.getElementById('sidebar');
    const closeBtn = document.getElementById('sidebar-close');
    const openBtn = document.getElementById('sidebar-open');
    
    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
    }
    
    closeBtn.addEventListener('click', toggleSidebar);
    openBtn.addEventListener('click', toggleSidebar);
}

// ============ 事件监听器初始化 ============
function initEventListeners() {
    // 搜索按钮
    document.getElementById('search-btn').addEventListener('click', searchPlace);
    document.getElementById('search-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') searchPlace();
    });
    
    // 省份选择
    document.getElementById('province-select').addEventListener('change', (e) => {
        onProvinceChange(e);
        updateVectorButtons();
    });
    
    // 城市选择
    document.getElementById('city-select').addEventListener('change', (e) => {
        onCityChange(e);
        updateVectorButtons();
    });
    
    // 区县选择
    document.getElementById('district-select').addEventListener('change', (e) => {
        onDistrictChange(e);
        updateVectorButtons();
    });
    
    // 加载边界按钮
    document.getElementById('load-boundary-btn').addEventListener('click', loadSelectedBoundary);
    
    // 缩放级别滑块
    document.getElementById('zoom-slider').addEventListener('input', function(e) {
        document.getElementById('zoom-value').textContent = e.target.value;
        if (currentBounds) {
            estimateDownload();
        }
    });
    
    // 下载按钮
    document.getElementById('download-btn').addEventListener('click', startDownload);
    
    // 矢量下载按钮
    document.getElementById('download-osm-btn').addEventListener('click', downloadOSMData);
    document.getElementById('download-admin-btn').addEventListener('click', downloadAdminBoundary);
    
    // 矢量加载/清除按钮
    document.getElementById('load-vector-btn').addEventListener('click', () => {
        document.getElementById('vector-file-input').click();
    });
    document.getElementById('vector-file-input').addEventListener('change', loadVectorFile);
    document.getElementById('clear-vector-btn').addEventListener('click', clearVectorLayers);
}

// ============ 地名搜索 ============
async function searchPlace() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;
    
    const resultsContainer = document.getElementById('search-results');
    resultsContainer.innerHTML = '<div class="search-result-item">搜索中...</div>';
    
    try {
        const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
        const results = await response.json();
        
        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="search-result-item">未找到结果</div>';
            return;
        }
        
        resultsContainer.innerHTML = results.map(r => `
            <div class="search-result-item" onclick="goToLocation(${r.lat}, ${r.lng}, ${r.bounds ? JSON.stringify(r.bounds).replace(/"/g, '&quot;') : 'null'}, ${r.address ? JSON.stringify(r.address).replace(/"/g, '&quot;') : 'null'})">
                <div class="name">${r.name}</div>
                <div class="detail">${r.display_name}</div>
            </div>
        `).join('');
    } catch (error) {
        resultsContainer.innerHTML = '<div class="search-result-item">搜索失败</div>';
        console.error('Search error:', error);
    }
}

function goToLocation(lat, lng, bounds, address) {
    if (bounds) {
        map.fitBounds([
            [bounds.south, bounds.west],
            [bounds.north, bounds.east]
        ]);
    } else {
        map.setView([lat, lng], 14);
    }
    document.getElementById('search-results').innerHTML = '';
    
    // 自动选择行政区划
    if (address) {
        autoSelectAdminRegion(address);
    }
}

async function autoSelectAdminRegion(address) {
    console.log("Auto-selecting admin region:", address);

    // 尝试匹配字段 (Nominatim 返回字段可能不同)
    const provinceText = address.state || address.province || address.region;
    const cityText = address.city || address.town || address.municipality || address.prefecture; 
    const districtText = address.district || address.county || address.city_district || address.suburb;

    // 1. 选择省份
    const provinceSelect = document.getElementById('province-select');
    const provOption = findOptionByText(provinceSelect, provinceText);
    
    if (provOption) {
        provinceSelect.value = provOption.value;
        // 触发变更并等待加载完成
        await onProvinceChange({ target: provinceSelect });
        
        // 2. 选择城市
        const citySelect = document.getElementById('city-select');
        let cityOption = findOptionByText(citySelect, cityText);
        
        // 直辖市特殊处理 (如 address.state="Beijing", address.city="Beijing")
        if (!cityOption && provinceText) {
             // 尝试再次用省份名匹配城市 (直辖市通常省市同名)
             cityOption = findOptionByText(citySelect, provinceText);
        }
        
        if (cityOption) {
            citySelect.value = cityOption.value;
            await onCityChange({ target: citySelect });
            
            // 3. 选择区县
            const districtSelect = document.getElementById('district-select');
            const distOption = findOptionByText(districtSelect, districtText);
            
            if (distOption) {
                districtSelect.value = distOption.value;
                onDistrictChange({ target: districtSelect });
            }
        }
    }
}

function findOptionByText(select, text) {
    if (!text) return null;
    // 移除常见后缀进行模糊匹配
    const cleanText = text.replace(/(省|市|区|县|Autonomus Region|Municipality)$/i, '').trim();
    if (!cleanText) return null;
    
    for (let i = 0; i < select.options.length; i++) {
        const opt = select.options[i];
        if (!opt.value) continue;
        
        // 双向包含匹配
        const optText = opt.text.replace(/(省|市|区|县)$/i, '').trim();
        if (optText.includes(cleanText) || cleanText.includes(optText)) {
            return opt;
        }
    }
    return null;
}

// ============ 行政区划 ============
async function loadProvinces() {
    try {
        const response = await fetch('/api/admin/provinces');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const provinces = await response.json();
        
        if (!Array.isArray(provinces)) {
            console.error('Provinces response is not an array:', provinces);
            return;
        }
        
        const select = document.getElementById('province-select');
        select.innerHTML = '<option value="">请选择省份</option>';
        provinces.forEach(p => {
            select.innerHTML += `<option value="${p.code}">${p.name}</option>`;
        });
    } catch (error) {
        console.error('Failed to load provinces:', error);
    }
}

async function onProvinceChange(e) {
    const code = e.target.value;
    const citySelect = document.getElementById('city-select');
    const districtSelect = document.getElementById('district-select');
    
    citySelect.innerHTML = '<option value="">请选择城市</option>';
    citySelect.disabled = true;
    districtSelect.innerHTML = '<option value="">请先选择城市</option>';
    districtSelect.disabled = true;
    
    if (!code) return;
    
    try {
        const response = await fetch(`/api/admin/cities?province_code=${code}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const cities = await response.json();
        
        if (!Array.isArray(cities)) {
            console.error('Cities response is not an array:', cities);
            return;
        }
        
        citySelect.disabled = false;
        cities.forEach(c => {
            citySelect.innerHTML += `<option value="${c.code}">${c.name}</option>`;
        });
    } catch (error) {
        console.error('Failed to load cities:', error);
    }
}

async function onCityChange(e) {
    const code = e.target.value;
    const districtSelect = document.getElementById('district-select');
    
    districtSelect.innerHTML = '<option value="">请选择区县</option>';
    districtSelect.disabled = true;
    
    if (!code) return;
    
    try {
        const response = await fetch(`/api/admin/districts?city_code=${code}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const districts = await response.json();
        
        if (!Array.isArray(districts)) {
            console.error('Districts response is not an array:', districts);
            return;
        }
        
        districtSelect.disabled = false;
        districts.forEach(d => {
            districtSelect.innerHTML += `<option value="${d.code}">${d.name}</option>`;
        });
    } catch (error) {
        console.error('Failed to load districts:', error);
    }
}

function onDistrictChange(e) {
    // 选择区县后可以加载边界
}

async function loadSelectedBoundary() {
    // 获取选中的代码
    const districtCode = document.getElementById('district-select').value;
    const cityCode = document.getElementById('city-select').value;
    const provinceCode = document.getElementById('province-select').value;
    
    const code = districtCode || cityCode || provinceCode;
    
    if (!code) {
        alert('请先选择行政区划');
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/boundary?code=${code}`);
        const geojson = await response.json();
        
        // 清除之前的图层
        drawnItems.clearLayers();
        if (boundaryLayer) {
            map.removeLayer(boundaryLayer);
        }
        
        // 添加边界
        boundaryLayer = L.geoJSON(geojson, {
            style: {
                color: '#e74c3c',
                fillColor: '#e74c3c',
                fillOpacity: 0.2,
                weight: 2
            }
        }).addTo(map);
        
        // 适应边界
        map.fitBounds(boundaryLayer.getBounds());
        
        // 设置当前边界
        const bounds = boundaryLayer.getBounds();
        currentBounds = {
            north: bounds.getNorth(),
            south: bounds.getSouth(),
            east: bounds.getEast(),
            west: bounds.getWest()
        };
        
        // 从 GeoJSON 中提取多边形坐标用于裁剪
        currentPolygon = extractPolygonFromGeoJSON(geojson);
        
        updateSelectionInfo();
        estimateDownload();
        updateVectorButtons();
    } catch (error) {
        console.error('Failed to load boundary:', error);
        alert('加载边界失败');
    }
}

// ============ 选择信息更新 ============
function updateSelectionInfo() {
    const infoDiv = document.getElementById('selection-info');
    
    if (!currentBounds) {
        infoDiv.innerHTML = '<p>使用地图工具绘制区域，或选择行政区划</p>';
        return;
    }
    
    const { north, south, east, west } = currentBounds;
    infoDiv.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.75rem;">
            <div><span style="color:#666">北:</span> <span class="coords">${north.toFixed(6)}°</span></div>
            <div><span style="color:#666">南:</span> <span class="coords">${south.toFixed(6)}°</span></div>
            <div><span style="color:#666">西:</span> <span class="coords">${west.toFixed(6)}°</span></div>
            <div><span style="color:#666">东:</span> <span class="coords">${east.toFixed(6)}°</span></div>
        </div>
    `;
}

// ============ 下载估算 ============
async function estimateDownload() {
    if (!currentBounds) return;
    
    const zoom = parseInt(document.getElementById('zoom-slider').value);
    const estimateDiv = document.getElementById('estimate-info');
    const downloadBtn = document.getElementById('download-btn');
    
    try {
        const response = await fetch('/api/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bounds: currentBounds,
                zoom: zoom,
                source: document.getElementById('source-select').value,
                format: document.getElementById('format-select').value
            })
        });
        
        const result = await response.json();
        
        if (result.allowed) {
            estimateDiv.className = 'estimate-info';
            estimateDiv.innerHTML = `
                <p>瓦片数量: <strong>${result.tile_count}</strong></p>
                <p>预估大小: <strong>~${result.estimated_size_mb} MB</strong></p>
            `;
            downloadBtn.disabled = false;
        } else {
            estimateDiv.className = 'estimate-info error';
            estimateDiv.innerHTML = `<p>${result.warning}</p>`;
            downloadBtn.disabled = true;
        }
    } catch (error) {
        estimateDiv.className = 'estimate-info error';
        estimateDiv.innerHTML = '<p>估算失败</p>';
        downloadBtn.disabled = true;
    }
}

// ============ 桌面端检测 ============
function isDesktopApp() {
    // pywebview 会注入 window.pywebview 对象
    return typeof window.pywebview !== 'undefined';
}

// ============ 下载 ============
async function startDownload() {
    if (!currentBounds) {
        alert('请先选择下载区域');
        return;
    }
    
    const downloadBtn = document.getElementById('download-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    // 获取文件格式和默认文件名
    const format = document.getElementById('format-select').value;
    const zoom = document.getElementById('zoom-slider').value;
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const ext = format === 'geotiff' ? '.tif' : format === 'png' ? '.png' : '.jpg';
    const defaultFilename = `map_${timestamp}_z${zoom}${ext}`;
    
    // 桌面端：先让用户选择保存路径
    let savePath = null;
    if (isDesktopApp()) {
        try {
            savePath = await window.pywebview.api.save_file_dialog(defaultFilename);
            if (!savePath) {
                // 用户取消了保存对话框
                return;
            }
        } catch (e) {
            console.error('保存对话框错误:', e);
            // 回退到网页方式
        }
    }
    
    // 禁用按钮，显示进度
    downloadBtn.disabled = true;
    downloadBtn.textContent = '⏳ 下载中...';
    progressContainer.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = '准备下载...';
    
    try {
        // Get proxy settings
        const useProxy = document.getElementById('proxy-checkbox').checked;
        const proxyUrl = document.getElementById('proxy-input').value.trim();
        
        const requestBody = {
            bounds: currentBounds,
            polygon: currentPolygon,
            zoom: parseInt(zoom),
            source: document.getElementById('source-select').value,
            format: format,
            crop_to_shape: document.getElementById('crop-checkbox').checked,
            proxy: useProxy && proxyUrl ? proxyUrl : null
        };
        
        // 第一步：创建下载任务
        const taskResponse = await fetch('/api/download_with_progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        if (!taskResponse.ok) {
            const error = await taskResponse.json();
            throw new Error(error.detail || '创建任务失败');
        }
        
        const { task_id, total } = await taskResponse.json();
        
        // 第二步：连接 SSE 获取进度
        const eventSource = new EventSource(`/api/download_progress/${task_id}`);
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const { status, progress, completed, total: totalTiles } = data;
            
            if (status === 'downloading') {
                progressFill.style.width = progress + '%';
                progressText.textContent = `下载中... ${completed}/${totalTiles} (${progress}%)`;
            } else if (status === 'merging') {
                progressFill.style.width = '95%';
                progressText.textContent = '拼接瓦片...';
            } else if (status === 'exporting') {
                progressFill.style.width = '98%';
                progressText.textContent = '生成文件...';
            } else if (status === 'completed') {
                progressFill.style.width = '100%';
                progressText.textContent = '保存文件...';
                eventSource.close();
                
                // 第三步：保存文件
                downloadFile(task_id, savePath);
            } else if (status === 'failed') {
                eventSource.close();
                alert(data.error || '下载失败');
                progressContainer.style.display = 'none';
                downloadBtn.textContent = '📥 下载地图';
                downloadBtn.disabled = false;
            }
        };
        
        eventSource.onerror = (error) => {
            eventSource.close();
            console.error('SSE error:', error);
            progressContainer.style.display = 'none';
            downloadBtn.textContent = '📥 下载地图';
            downloadBtn.disabled = false;
            alert('进度连接失败');
        };
        
    } catch (error) {
        progressContainer.style.display = 'none';
        downloadBtn.textContent = '📥 下载地图';
        downloadBtn.disabled = false;
        alert('下载失败: ' + error.message);
    }
}

async function downloadFile(taskId, savePath = null) {
    const downloadBtn = document.getElementById('download-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressText = document.getElementById('progress-text');
    
    try {
        // 桌面端：直接保存到指定路径
        if (savePath && isDesktopApp()) {
            const response = await fetch(`/api/save_to_file/${taskId}?save_path=${encodeURIComponent(savePath)}`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '保存文件失败');
            }
            
            const result = await response.json();
            progressText.textContent = `已保存到: ${result.path}`;
            
            // 完成
            setTimeout(() => {
                progressContainer.style.display = 'none';
                downloadBtn.textContent = '📥 下载地图';
                downloadBtn.disabled = false;
            }, 3000);
            return;
        }
        
        // 网页端：通过浏览器下载
        const response = await fetch(`/api/download_result/${taskId}`);
        
        if (!response.ok) {
            throw new Error('获取文件失败');
        }
        
        // 获取文件名
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'map.tif';
        if (contentDisposition) {
            const match = contentDisposition.match(/filename=(.+)/);
            if (match) filename = match[1];
        }
        
        // 下载文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        // 完成
        setTimeout(() => {
            progressContainer.style.display = 'none';
            downloadBtn.textContent = '📥 下载地图';
            downloadBtn.disabled = false;
        }, 2000);
        
    } catch (error) {
        progressContainer.style.display = 'none';
        downloadBtn.textContent = '📥 下载地图';
        downloadBtn.disabled = false;
        alert('保存文件失败: ' + error.message);
    }
}

// ============ 矢量数据下载 ============

// 当前选中的行政区划代码
let currentAdminCode = null;

function updateVectorButtons() {
    const osmBtn = document.getElementById('download-osm-btn');
    const adminBtn = document.getElementById('download-admin-btn');
    const statusEl = document.getElementById('vector-status');
    
    // OSM 下载需要有边界框
    osmBtn.disabled = !currentBounds;
    
    // 行政区划下载需要选中行政区
    const districtCode = document.getElementById('district-select').value;
    const cityCode = document.getElementById('city-select').value;
    const provinceCode = document.getElementById('province-select').value;
    currentAdminCode = districtCode || cityCode || provinceCode;
    adminBtn.disabled = !currentAdminCode;
    
    // 更新状态提示
    if (currentBounds && currentAdminCode) {
        statusEl.textContent = '✅ 可下载 OSM 和行政边界';
    } else if (currentBounds) {
        statusEl.textContent = '✅ 可下载 OSM（选择行政区可下载边界）';
    } else if (currentAdminCode) {
        statusEl.textContent = '✅ 可下载行政边界（绘制区域可下载 OSM）';
    } else {
        statusEl.textContent = '绘制区域或选择行政区划后可下载';
    }
}

async function downloadOSMData() {
    if (!currentBounds) {
        alert('请先绘制或选择一个区域');
        return;
    }
    
    const featureType = document.getElementById('osm-feature-select').value;
    const statusEl = document.getElementById('vector-status');
    const osmBtn = document.getElementById('download-osm-btn');
    
    // 生成文件名
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const defaultFilename = `osm_${featureType}_${timestamp}.geojson`;
    
    // 桌面端：弹出保存对话框
    let savePath = null;
    if (isDesktopApp()) {
        try {
            savePath = await window.pywebview.api.save_file_dialog(defaultFilename);
            if (!savePath) return; // 用户取消
        } catch (e) {
            console.error('保存对话框错误:', e);
        }
    }
    
    osmBtn.disabled = true;
    statusEl.textContent = '⬇️ 正在下载 OSM 数据...';
    
    try {
        // 获取代理设置
        const useProxy = document.getElementById('proxy-checkbox').checked;
        const proxyUrl = document.getElementById('proxy-input').value.trim();
        const proxy = useProxy && proxyUrl ? proxyUrl : '';
        
        const params = new URLSearchParams({
            feature_type: featureType,
            south: currentBounds.south,
            west: currentBounds.west,
            north: currentBounds.north,
            east: currentBounds.east,
            output_format: 'geojson',
            proxy: proxy
        });
        
        const response = await fetch(`/api/vector/osm?${params}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'OSM 下载失败');
        }
        
        const content = await response.text();
        const filename = response.headers.get('X-Filename') || defaultFilename;
        
        // 保存文件
        if (savePath && isDesktopApp()) {
            // 桌面端：直接写入文件
            const saveResponse = await fetch('/api/vector/save_to_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: content, save_path: savePath, filename: filename })
            });
            
            if (saveResponse.ok) {
                statusEl.textContent = `✅ 已保存: ${savePath}`;
            } else {
                const err = await saveResponse.json();
                throw new Error(err.detail || '保存文件失败');
            }
        } else {
            // 网页端：通过浏览器下载
            downloadTextFile(content, filename, 'application/geo+json');
            statusEl.textContent = `✅ 下载完成: ${filename}`;
        }
        
    } catch (error) {
        statusEl.textContent = `❌ ${error.message}`;
        alert('OSM 下载失败: ' + error.message);
    } finally {
        osmBtn.disabled = false;
        setTimeout(() => updateVectorButtons(), 3000);
    }
}

async function downloadAdminBoundary() {
    if (!currentAdminCode) {
        alert('请先选择行政区划');
        return;
    }
    
    const statusEl = document.getElementById('vector-status');
    const adminBtn = document.getElementById('download-admin-btn');
    
    // 生成文件名
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const defaultFilename = `admin_${currentAdminCode}_${timestamp}.geojson`;
    
    // 桌面端：弹出保存对话框
    let savePath = null;
    if (isDesktopApp()) {
        try {
            savePath = await window.pywebview.api.save_file_dialog(defaultFilename);
            if (!savePath) return;
        } catch (e) {
            console.error('保存对话框错误:', e);
        }
    }
    
    adminBtn.disabled = true;
    statusEl.textContent = '⬇️ 正在下载行政边界...';
    
    try {
        const params = new URLSearchParams({
            code: currentAdminCode,
            output_format: 'geojson',
            full: 'true'
        });
        
        const response = await fetch(`/api/vector/admin_boundary?${params}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '下载失败');
        }
        
        const content = await response.text();
        const filename = response.headers.get('X-Filename') || defaultFilename;
        
        // 保存文件
        if (savePath && isDesktopApp()) {
            const saveResponse = await fetch('/api/vector/save_to_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: content, save_path: savePath, filename: filename })
            });
            
            if (saveResponse.ok) {
                statusEl.textContent = `✅ 已保存: ${savePath}`;
            } else {
                const err = await saveResponse.json();
                throw new Error(err.detail || '保存文件失败');
            }
        } else {
            downloadTextFile(content, filename, 'application/geo+json');
            statusEl.textContent = `✅ 下载完成: ${filename}`;
        }
        
    } catch (error) {
        statusEl.textContent = `❌ ${error.message}`;
        alert('边界下载失败: ' + error.message);
    } finally {
        adminBtn.disabled = false;
        setTimeout(() => updateVectorButtons(), 3000);
    }
}

function downloadTextFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// ============ 矢量数据加载 ============

// 存储加载的矢量图层
let vectorLayers = [];

async function loadVectorFile(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const statusEl = document.getElementById('vector-status');
    statusEl.textContent = '⬇️ 正在加载...';
    
    for (const file of files) {
        try {
            const filename = file.name.toLowerCase();
            let geojson;
            
            if (filename.endsWith('.geojson') || filename.endsWith('.json')) {
                // 直接读取 GeoJSON
                const text = await file.text();
                geojson = JSON.parse(text);
            } else if (filename.endsWith('.zip')) {
                // Shapefile ZIP - 需要后端处理
                statusEl.textContent = '⚠️ Shapefile 需要通过后端转换...';
                geojson = await convertShapefileToGeoJSON(file);
            } else {
                throw new Error('不支持的文件格式');
            }
            
            if (geojson) {
                addVectorToMap(geojson, file.name);
            }
        } catch (error) {
            console.error('Failed to load vector file:', error);
            statusEl.textContent = `❌ 加载失败: ${error.message}`;
        }
    }
    
    // 清空文件输入，允许重新选择相同文件
    event.target.value = '';
}

function addVectorToMap(geojson, filename) {
    const statusEl = document.getElementById('vector-status');
    
    // 随机颜色
    const colors = ['#e74c3c', '#3498db', '#2ecc71', '#9b59b6', '#f39c12', '#1abc9c'];
    const color = colors[vectorLayers.length % colors.length];
    
    // 创建图层
    const layer = L.geoJSON(geojson, {
        style: {
            color: color,
            fillColor: color,
            fillOpacity: 0.3,
            weight: 2
        },
        pointToLayer: function(feature, latlng) {
            return L.circleMarker(latlng, {
                radius: 6,
                fillColor: color,
                color: '#fff',
                weight: 1,
                fillOpacity: 0.8
            });
        },
        onEachFeature: function(feature, layer) {
            // 添加弹窗显示属性
            if (feature.properties) {
                const props = Object.entries(feature.properties)
                    .filter(([k, v]) => v !== null && v !== '')
                    .slice(0, 10)  // 最多显示10个属性
                    .map(([k, v]) => `<b>${k}:</b> ${v}`)
                    .join('<br>');
                if (props) {
                    layer.bindPopup(props);
                }
            }
        }
    }).addTo(map);
    
    vectorLayers.push({ layer, filename });
    
    // 缩放到图层范围
    try {
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds);
            
            // 设置当前边界（用于下载）
            currentBounds = {
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest()
            };
            updateSelectionInfo();
            updateVectorButtons();
        }
    } catch (e) {
        console.error('Could not fit bounds:', e);
    }
    
    // 统计要素数量
    let featureCount = 0;
    if (geojson.type === 'FeatureCollection') {
        featureCount = geojson.features ? geojson.features.length : 0;
    } else if (geojson.type === 'Feature') {
        featureCount = 1;
    }
    
    statusEl.textContent = `✅ 已加载: ${filename} (${featureCount} 个要素)`;
}

function clearVectorLayers() {
    vectorLayers.forEach(({ layer }) => {
        map.removeLayer(layer);
    });
    vectorLayers = [];
    
    document.getElementById('vector-status').textContent = '已清除所有矢量图层';
}

async function convertShapefileToGeoJSON(file) {
    // 发送到后端转换
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/vector/convert_shapefile', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Shapefile 转换失败');
    }
    
    return await response.json();
}
