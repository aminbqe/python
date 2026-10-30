<?php
// Download relay only: never extracts or executes uploaded HDL/ZIP content.
declare(strict_types=1);
ini_set('display_errors', '0');
ini_set('zlib.output_compression', '0');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
const MAX_BYTES = 524288;
const TTL = 1800;
function fail(int $status, string $message): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error' => $message], JSON_UNESCAPED_UNICODE);
    exit;
}
$dir = sys_get_temp_dir() . '/fpga_exports_' . substr(hash('sha256', __DIR__), 0, 16);
if (!is_dir($dir) && !@mkdir($dir, 0700, true) && !is_dir($dir)) {
    fail(503, 'فضای موقت دانلود در دسترس نیست');
}
$method = $_SERVER['REQUEST_METHOD'];
if ($method === 'POST') {
    if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > MAX_BYTES) fail(413, 'حجم پروژه بیش از حد مجاز است');
    $data = file_get_contents('php://input', false, null, 0, MAX_BYTES + 1);
    if ($data === false || strlen($data) < 22 || strlen($data) > MAX_BYTES || substr($data, 0, 4) !== "PK\x03\x04") {
        fail(400, 'فایل ZIP معتبر نیست');
    }
    // Serialize retention/quota checks across concurrent uploads.
    $lock = fopen($dir . '/.lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX)) fail(503, 'لطفاً دوباره تلاش کنید');
    $files = glob($dir . '/*.zip') ?: [];
    $count = 0;
    foreach ($files as $file) {
        if (time() - filemtime($file) > TTL) @unlink($file); else $count++;
    }
    if ($count >= 128) { flock($lock, LOCK_UN); fclose($lock); fail(429, 'ظرفیت موقت پر است؛ بعداً تلاش کنید'); }
    $token = bin2hex(random_bytes(24));
    $written = file_put_contents($dir . '/' . $token . '.zip', $data, LOCK_EX);
    @chmod($dir . '/' . $token . '.zip', 0600);
    flock($lock, LOCK_UN); fclose($lock);
    if ($written !== strlen($data)) fail(503, 'ذخیرهٔ فایل ناموفق بود');
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['url' => './download.php?file=' . $token . '.zip']);
    exit;
}
if ($method !== 'GET' && $method !== 'HEAD') {
    header('Allow: GET, HEAD, POST'); fail(405, 'روش درخواست پشتیبانی نمی‌شود');
}
$name = $_GET['file'] ?? '';
if (!is_string($name) || !preg_match('/\A[a-f0-9]{48}\.zip\z/', $name)) fail(404, 'فایل پیدا نشد');
$path = $dir . '/' . $name;
if (!is_file($path) || time() - filemtime($path) > TTL) fail(404, 'لینک منقضی شده؛ پروژه را دوباره آماده کنید');
$size = filesize($path); $start = 0; $end = $size - 1;
header('Accept-Ranges: bytes');
header('Content-Type: application/zip');
$filename = $_GET['name'] ?? 'AX309_lab_project.zip';
if (!is_string($filename) || !preg_match('/\A\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.zip\z/', $filename)) {
    $filename = 'AX309_lab_project.zip';
}
header('Content-Disposition: attachment; filename="' . $filename . '"');
if ($method === 'GET' && isset($_SERVER['HTTP_RANGE'])) {
    if (!preg_match('/\Abytes=(\d*)-(\d*)\z/', $_SERVER['HTTP_RANGE'], $range) || ($range[1] === '' && $range[2] === '')) {
        header('Content-Range: bytes */' . $size); http_response_code(416); exit;
    }
    if ($range[1] === '') $start = max(0, $size - (int)$range[2]);
    else { $start = (int)$range[1]; if ($range[2] !== '') $end = min($end, (int)$range[2]); }
    if ($start > $end || $start >= $size) { header('Content-Range: bytes */' . $size); http_response_code(416); exit; }
    http_response_code(206);
    header('Content-Range: bytes ' . $start . '-' . $end . '/' . $size);
}
header('Content-Length: ' . ($end - $start + 1));
if ($method === 'HEAD') exit;
$handle = fopen($path, 'rb');
if ($handle === false) exit;
fseek($handle, $start);
$remaining = $end - $start + 1;
while ($remaining > 0 && !feof($handle)) {
    $chunk = fread($handle, min(65536, $remaining));
    if ($chunk === false || $chunk === '') break;
    echo $chunk; $remaining -= strlen($chunk);
}
fclose($handle);
