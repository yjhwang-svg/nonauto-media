/**
 * 수기매체 자동화 - 날짜 지정 재실행 웹앱
 *
 * [배포 방법]
 * 1. script.google.com → 새 프로젝트
 * 2. Code.gs, index.html 파일을 붙여넣기
 * 3. 프로젝트 설정(톱니바퀴) → 스크립트 속성 → 아래 두 값 추가
 *    GITHUB_TOKEN  : ghp_xxxx (repo + workflow 권한)
 *    GITHUB_REPO   : yjhwang-svg/nonauto-media
 * 4. 배포 → 새 배포 → 웹앱
 *    - 실행 계정 : 나(스크립트 소유자)
 *    - 액세스 권한 : 모든 사용자
 * 5. 배포 URL을 Slack 메시지에 연결
 */

var WORKFLOW_FILE = "daily_crawl.yml";

function doGet() {
  return HtmlService.createHtmlOutputFromFile("index")
    .setTitle("수기매체 자동화 재실행")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * 클라이언트(index.html)에서 호출. targetDate: "YYYY-MM-DD"
 */
function triggerWorkflow(targetDate) {
  var props  = PropertiesService.getScriptProperties();
  var token  = props.getProperty("GITHUB_TOKEN");
  var repo   = props.getProperty("GITHUB_REPO") || "yjhwang-svg/nonauto-media";

  if (!token) {
    return { success: false, message: "GITHUB_TOKEN이 스크립트 속성에 없습니다." };
  }

  var url = "https://api.github.com/repos/" + repo + "/actions/workflows/" + WORKFLOW_FILE + "/dispatches";

  var options = {
    method: "post",
    headers: {
      "Authorization": "Bearer " + token,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    payload: JSON.stringify({
      ref: "main",
      inputs: {
        target_date: targetDate,
        allow_partial_upload: "1"
      }
    }),
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(url, options);
  var code     = response.getResponseCode();

  if (code === 204) {
    return { success: true, message: targetDate + " 재실행이 시작됐습니다.\n약 3~5분 후 완료됩니다." };
  } else {
    return { success: false, message: "실행 실패 (HTTP " + code + ")\n" + response.getContentText() };
  }
}
