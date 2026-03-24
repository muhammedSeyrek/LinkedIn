package main

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-rod/rod"
	"github.com/go-rod/rod/lib/launcher"
	"github.com/go-rod/stealth"
	"github.com/google/uuid"
)

// ── Types ─────────────────────────────────────────────────────────────────────

type Job struct {
	Title      string `json:"title"`
	Company    string `json:"company"`
	Location   string `json:"location"`
	Link       string `json:"link"`
	DatePosted string `json:"date_posted"`
}

type SearchParams struct {
	Keywords         string   `json:"keywords"          form:"keywords"`
	Location         string   `json:"location"          form:"location"`
	MaxPages         int      `json:"max_pages"         form:"max_pages"`
	Email            string   `json:"email"             form:"email"`
	Password         string   `json:"-"                 form:"password"`
	JobTypes         []string `json:"job_types"         form:"job_types"`
	ExperienceLevels []string `json:"experience_levels" form:"experience_levels"`
	RemoteOptions    []string `json:"remote_options"    form:"remote_options"`
	DatePosted       string   `json:"date_posted"       form:"date_posted"`
}

type JobRecord struct {
	ID         string       `json:"id"`
	Status     string       `json:"status"`
	Progress   float64      `json:"progress"`
	Page       int          `json:"page"`
	TotalPages int          `json:"total_pages"`
	FoundJobs  int          `json:"found_jobs"`
	Message    string       `json:"message"`
	Error      string       `json:"error,omitempty"`
	CreatedAt  string       `json:"created_at"`
	Params     SearchParams `json:"params"`
	ResultFile string       `json:"result_file,omitempty"`
}

type FlashMsg struct {
	Category string
	Message  string
}

// ── State ─────────────────────────────────────────────────────────────────────

var (
	jobStore  = map[string]*JobRecord{}
	jobsMu    sync.RWMutex
	flashData = map[string][]FlashMsg{}
	flashMu   sync.Mutex
)

func getJob(id string) (*JobRecord, bool) {
	jobsMu.RLock()
	defer jobsMu.RUnlock()
	j, ok := jobStore[id]
	return j, ok
}

func setJob(j *JobRecord) {
	jobsMu.Lock()
	defer jobsMu.Unlock()
	jobStore[j.ID] = j
}

func updateJob(id string, fn func(*JobRecord)) {
	jobsMu.Lock()
	defer jobsMu.Unlock()
	if j, ok := jobStore[id]; ok {
		fn(j)
	}
}

func allJobs() []*JobRecord {
	jobsMu.RLock()
	defer jobsMu.RUnlock()
	out := make([]*JobRecord, 0, len(jobStore))
	for _, j := range jobStore {
		out = append(out, j)
	}
	return out
}

// ── Flash ─────────────────────────────────────────────────────────────────────

func pushFlash(c *gin.Context, cat, msg string) {
	id := uuid.New().String()
	flashMu.Lock()
	flashData[id] = []FlashMsg{{cat, msg}}
	flashMu.Unlock()
	c.SetCookie("flash", id, 30, "/", "", false, false)
}

func popFlash(c *gin.Context) []FlashMsg {
	id, err := c.Cookie("flash")
	if err != nil {
		return nil
	}
	c.SetCookie("flash", "", -1, "/", "", false, false)
	flashMu.Lock()
	msgs := flashData[id]
	delete(flashData, id)
	flashMu.Unlock()
	return msgs
}

// ── Templates ─────────────────────────────────────────────────────────────────

var funcMap = template.FuncMap{
	"jobTypeName": func(t string) string {
		m := map[string]string{"F": "Tam Zamanlı", "P": "Yarı Zamanlı", "C": "Sözleşmeli", "T": "Geçici", "I": "Staj"}
		if n, ok := m[t]; ok {
			return n
		}
		return t
	},
	"remoteOptionName": func(o string) string {
		m := map[string]string{"1": "Uzaktan", "2": "Hibrit", "3": "Ofiste"}
		if n, ok := m[o]; ok {
			return n
		}
		return o
	},
	"toJSON": func(v interface{}) template.JS {
		b, err := json.Marshal(v)
		if err != nil {
			return template.JS("{}")
		}
		return template.JS(b)
	},
	"truncate": func(s string, n int) string {
		r := []rune(s)
		if len(r) <= n {
			return s
		}
		return string(r[:n]) + "…"
	},
	"lower": strings.ToLower,
	"add":   func(a, b int) int { return a + b },
}

func renderPage(c *gin.Context, page string, data gin.H) {
	tmpl, err := template.New("").Funcs(funcMap).ParseFiles(
		"templates/base.html",
		"templates/"+page+".html",
	)
	if err != nil {
		c.String(500, "Template parse error: %v", err)
		return
	}
	c.Header("Content-Type", "text/html; charset=utf-8")
	if err := tmpl.ExecuteTemplate(c.Writer, "base", data); err != nil {
		log.Printf("Template render error: %v", err)
	}
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	os.MkdirAll("logs", 0755)
	os.MkdirAll("static/results", 0755)
	os.MkdirAll("temp", 0755)

	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()
	r.Static("/static", "./static")

	r.GET("/", indexHandler)
	r.POST("/start_search", startSearchHandler)
	r.GET("/job_status/:id", jobStatusPageHandler)
	r.GET("/api/job_status/:id", apiJobStatusHandler)
	r.GET("/jobs", jobsListHandler)
	r.GET("/download/:id", downloadHandler)
	r.POST("/delete_job/:id", deleteJobHandler)

	log.Println("LinkedIn scraper başlatıldı — http://0.0.0.0:5000")
	r.Run(":5000")
}

// ── Handlers ──────────────────────────────────────────────────────────────────

func indexHandler(c *gin.Context) {
	renderPage(c, "index", gin.H{"CurrentPage": "index", "Flash": popFlash(c)})
}

func startSearchHandler(c *gin.Context) {
	var params SearchParams
	if err := c.ShouldBind(&params); err != nil {
		pushFlash(c, "danger", "Form hatası: "+err.Error())
		c.Redirect(302, "/")
		return
	}
	if strings.TrimSpace(params.Keywords) == "" {
		pushFlash(c, "danger", "Anahtar kelimeler zorunludur")
		c.Redirect(302, "/")
		return
	}
	if params.MaxPages < 1 {
		params.MaxPages = 5
	}
	if params.MaxPages > 20 {
		params.MaxPages = 20
	}

	rec := &JobRecord{
		ID:         uuid.New().String(),
		Status:     "pending",
		CreatedAt:  time.Now().Format("2006-01-02 15:04:05"),
		Params:     params,
		TotalPages: params.MaxPages,
	}
	setJob(rec)
	go runScraper(rec.ID, params)

	pushFlash(c, "success", "Arama başlatıldı! İlerlemeyi kontrol sayfasından takip edebilirsiniz.")
	c.Redirect(302, "/job_status/"+rec.ID)
}

func jobStatusPageHandler(c *gin.Context) {
	id := c.Param("id")
	job, ok := getJob(id)
	if !ok {
		pushFlash(c, "danger", "Belirtilen arama bulunamadı.")
		c.Redirect(302, "/jobs")
		return
	}
	renderPage(c, "status", gin.H{
		"CurrentPage": "jobs",
		"JobID":       id,
		"Job":         job,
		"Flash":       popFlash(c),
	})
}

func apiJobStatusHandler(c *gin.Context) {
	id := c.Param("id")
	job, ok := getJob(id)
	if !ok {
		c.JSON(404, gin.H{"error": "not found"})
		return
	}
	jobsMu.RLock()
	c.JSON(200, job)
	jobsMu.RUnlock()
}

func jobsListHandler(c *gin.Context) {
	renderPage(c, "jobs", gin.H{
		"CurrentPage": "jobs",
		"Jobs":        allJobs(),
		"Flash":       popFlash(c),
	})
}

func downloadHandler(c *gin.Context) {
	id := c.Param("id")
	job, ok := getJob(id)
	if !ok || job.ResultFile == "" {
		pushFlash(c, "danger", "Dosya bulunamadı.")
		c.Redirect(302, "/jobs")
		return
	}
	filename := filepath.Base(job.ResultFile)
	c.Header("Content-Disposition", "attachment; filename="+filename)
	c.Header("Content-Type", "text/csv; charset=utf-8")
	c.File(job.ResultFile)
}

func deleteJobHandler(c *gin.Context) {
	id := c.Param("id")
	jobsMu.Lock()
	delete(jobStore, id)
	jobsMu.Unlock()
	pushFlash(c, "success", "Arama silindi.")
	c.Redirect(302, "/jobs")
}

// ── Scraper ───────────────────────────────────────────────────────────────────

func buildSearchURL(p SearchParams) string {
	u, _ := url.Parse("https://www.linkedin.com/jobs/search/")
	q := u.Query()
	q.Set("keywords", p.Keywords)
	if p.Location != "" {
		q.Set("location", p.Location)
	}
	if len(p.JobTypes) > 0 {
		q.Set("f_JT", strings.Join(p.JobTypes, ","))
	}
	if len(p.ExperienceLevels) > 0 {
		q.Set("f_E", strings.Join(p.ExperienceLevels, ","))
	}
	if len(p.RemoteOptions) > 0 {
		q.Set("f_WT", strings.Join(p.RemoteOptions, ","))
	}
	if p.DatePosted != "" {
		q.Set("f_TPR", p.DatePosted)
	}
	u.RawQuery = q.Encode()
	return u.String()
}

func newBrowser() (*rod.Browser, func(), error) {
	l := launcher.New().
		Set("no-sandbox", "").
		Set("disable-dev-shm-usage", "").
		Set("disable-gpu", "").
		Headless(true)

	if chromePath := os.Getenv("CHROME_BIN"); chromePath != "" {
		l = l.Bin(chromePath)
	} else if path, found := launcher.LookPath(); found {
		l = l.Bin(path)
	}

	browserURL, err := l.Launch()
	if err != nil {
		return nil, nil, fmt.Errorf("tarayıcı başlatılamadı: %w", err)
	}
	browser := rod.New().ControlURL(browserURL)
	if err := browser.Connect(); err != nil {
		l.Cleanup()
		return nil, nil, fmt.Errorf("bağlantı kurulamadı: %w", err)
	}
	return browser, func() { browser.MustClose(); l.Cleanup() }, nil
}

func isBlocked(page *rod.Page) bool {
	info, err := page.Info()
	if err != nil {
		return false
	}
	if strings.Contains(info.URL, "/checkpoint/") || strings.Contains(info.URL, "/authwall/") {
		log.Printf("[BOT] Engel URL: %s", info.URL)
		return true
	}
	// If page title shows job results → definitely not blocked
	title := info.Title
	if strings.Contains(strings.ToLower(title), "jobs") || strings.Contains(title, "ilan") {
		for _, ch := range title {
			if ch >= '0' && ch <= '9' {
				return false
			}
		}
	}
	// Check visible text (not HTML attributes)
	res, err := page.Eval(`() => document.body ? document.body.innerText.toLowerCase() : ""`)
	if err != nil {
		return false
	}
	text := res.Value.Str()
	for _, phrase := range []string{
		"are you a robot", "unusual traffic",
		"verify you are human", "let's do a quick security check",
	} {
		if strings.Contains(text, phrase) {
			log.Printf("[BOT] Görünür metin: %s", phrase)
			return true
		}
	}
	return false
}

func runScraper(jobID string, params SearchParams) {
	updateJob(jobID, func(j *JobRecord) { j.Status = "running"; j.Message = "Tarayıcı başlatılıyor..." })

	browser, cleanup, err := newBrowser()
	if err != nil {
		updateJob(jobID, func(j *JobRecord) { j.Status = "failed"; j.Error = err.Error(); j.Message = j.Error })
		return
	}
	defer cleanup()

	if params.Email != "" && params.Password != "" {
		updateJob(jobID, func(j *JobRecord) { j.Message = "LinkedIn'e giriş yapılıyor..." })
		loginLinkedIn(browser, params.Email, params.Password)
	}

	page := stealth.MustPage(browser)
	defer page.MustClose()

	updateJob(jobID, func(j *JobRecord) { j.Message = "Arama sayfası yükleniyor..." })
	if err := page.Navigate(buildSearchURL(params)); err != nil {
		updateJob(jobID, func(j *JobRecord) { j.Status = "failed"; j.Error = "Sayfa yüklenemedi: " + err.Error(); j.Message = j.Error })
		return
	}
	page.MustWaitLoad()
	time.Sleep(2 * time.Second)

	var allFound []Job

	for cur := 1; cur <= params.MaxPages; cur++ {
		updateJob(jobID, func(j *JobRecord) {
			j.Page = cur
			j.Progress = float64(cur-1) / float64(params.MaxPages) * 100
			j.Message = fmt.Sprintf("Sayfa %d / %d taranıyor...", cur, params.MaxPages)
		})

		if isBlocked(page) {
			updateJob(jobID, func(j *JobRecord) {
				j.Status = "failed"
				j.Error = "LinkedIn tarafından engellendiniz."
				j.Message = j.Error
			})
			return
		}

		pageJobs := extractJobsFromPage(page)
		allFound = append(allFound, pageJobs...)
		log.Printf("Sayfa %d: %d ilan (toplam: %d)", cur, len(pageJobs), len(allFound))
		updateJob(jobID, func(j *JobRecord) { j.FoundJobs = len(allFound) })

		if cur < params.MaxPages {
			if !goToNextPage(page) {
				log.Printf("Sonraki sayfa yok, sayfa %d'de duruldu", cur)
				break
			}
			time.Sleep(2 * time.Second)
		}
	}

	timestamp := time.Now().Format("20060102_150405")
	filename := fmt.Sprintf("static/results/linkedin_jobs_%s_%s.csv", jobID, timestamp)
	if err := saveCSV(allFound, filename); err != nil {
		log.Printf("CSV kaydetme hatası: %v", err)
	}

	updateJob(jobID, func(j *JobRecord) {
		j.Status = "completed"
		j.Progress = 100
		j.FoundJobs = len(allFound)
		j.ResultFile = filename
		j.Message = fmt.Sprintf("Arama tamamlandı! %d ilan bulundu.", len(allFound))
	})
}

func loginLinkedIn(browser *rod.Browser, email, password string) bool {
	page := stealth.MustPage(browser)
	defer page.MustClose()

	if err := page.Navigate("https://www.linkedin.com/login"); err != nil {
		return false
	}
	page.MustWaitLoad()
	time.Sleep(1500 * time.Millisecond)

	emailEl, err := page.Element("#username")
	if err != nil {
		return false
	}
	emailEl.MustInput(email)

	passEl, err := page.Element("#password")
	if err != nil {
		return false
	}
	passEl.MustInput(password)

	if btn, err := page.Element("button[type='submit']"); err == nil {
		btn.MustClick()
	}
	page.MustWaitLoad()
	time.Sleep(2 * time.Second)
	return !isBlocked(page)
}

func extractJobsFromPage(page *rod.Page) []Job {
	// Gradually scroll to load lazy-rendered cards
	page.MustEval(`async () => {
		for (let y = 0; y < document.body.scrollHeight; y += 400) {
			window.scrollTo(0, y);
			await new Promise(r => setTimeout(r, 120));
		}
	}`)
	time.Sleep(1500 * time.Millisecond)

	var cards rod.Elements
	for _, sel := range []string{
		"li[data-occludable-job-id]",
		".jobs-search-results__list-item",
		".scaffold-layout__list-item",
		".job-search-card",
	} {
		els, err := page.Elements(sel)
		if err == nil && len(els) > 0 {
			cards = els
			break
		}
	}

	jobs := make([]Job, 0, len(cards))
	for _, card := range cards {
		j := extractJobFromCard(card)
		if j.Title != "" {
			jobs = append(jobs, j)
		}
	}
	return jobs
}

func extractJobFromCard(card *rod.Element) Job {
	var j Job

	for _, sel := range []string{
		".job-card-list__title--link",
		".job-card-list__title",
		".job-card-container__link",
		"h3 a",
	} {
		el, err := card.Element(sel)
		if err != nil {
			continue
		}
		text, _ := el.Text()
		if strings.TrimSpace(text) == "" {
			continue
		}
		j.Title = strings.TrimSpace(text)
		href, _ := el.Attribute("href")
		if href != nil {
			if strings.HasPrefix(*href, "http") {
				j.Link = *href
			} else {
				j.Link = "https://www.linkedin.com" + *href
			}
		}
		break
	}

	for _, sel := range []string{
		".job-card-container__primary-description",
		".job-card-container__company-name",
		"h4 a",
	} {
		el, err := card.Element(sel)
		if err != nil {
			continue
		}
		text, _ := el.Text()
		if t := strings.TrimSpace(text); t != "" {
			j.Company = t
			break
		}
	}

	for _, sel := range []string{
		".job-card-container__metadata-item",
		".artdeco-entity-lockup__caption",
	} {
		el, err := card.Element(sel)
		if err != nil {
			continue
		}
		text, _ := el.Text()
		if t := strings.TrimSpace(text); t != "" {
			j.Location = t
			break
		}
	}

	if el, err := card.Element("time"); err == nil {
		dt, _ := el.Attribute("datetime")
		if dt != nil && *dt != "" {
			j.DatePosted = *dt
		} else if text, _ := el.Text(); text != "" {
			j.DatePosted = strings.TrimSpace(text)
		}
	}

	return j
}

func goToNextPage(page *rod.Page) bool {
	for _, sel := range []string{
		"button[aria-label='Next']:not([disabled])",
		".artdeco-pagination__button--next:not([disabled])",
	} {
		el, err := page.Element(sel)
		if err != nil {
			continue
		}
		disabled, _ := el.Attribute("disabled")
		if disabled != nil {
			continue
		}
		el.MustScrollIntoView()
		time.Sleep(500 * time.Millisecond)
		el.MustClick()
		page.MustWaitLoad()
		return true
	}
	return false
}

func saveCSV(jobs []Job, filename string) error {
	f, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer f.Close()
	f.Write([]byte{0xEF, 0xBB, 0xBF}) // UTF-8 BOM for Excel

	w := csv.NewWriter(f)
	defer w.Flush()
	_ = w.Write([]string{"title", "company", "location", "link", "date_posted"})
	for _, j := range jobs {
		_ = w.Write([]string{j.Title, j.Company, j.Location, j.Link, j.DatePosted})
	}
	return nil
}
