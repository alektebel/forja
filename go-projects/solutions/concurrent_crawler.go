package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

type crawlJob struct {
	url   string
	depth int
}

type PageResult struct {
	URL        string
	Depth      int
	StatusCode int
	LinksFound int
	Error      string
}

type Crawler struct {
	client    *http.Client
	workers   int
	maxDepth  int
	sameHost  bool
	hrefRegex *regexp.Regexp
	visited   map[string]struct{}
	mu        sync.Mutex
}

func NewCrawler(timeout time.Duration, workers, maxDepth int, sameHost bool) *Crawler {
	if workers < 1 {
		workers = 1
	}
	return &Crawler{
		client:    &http.Client{Timeout: timeout},
		workers:   workers,
		maxDepth:  maxDepth,
		sameHost:  sameHost,
		hrefRegex: regexp.MustCompile(`(?i)href\s*=\s*['"]([^'"#]+)['"]`),
		visited:   make(map[string]struct{}),
	}
}

func (c *Crawler) markVisited(rawURL string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, exists := c.visited[rawURL]; exists {
		return false
	}
	c.visited[rawURL] = struct{}{}
	return true
}

func (c *Crawler) normalizeLink(base *url.URL, raw string, allowedHost string) (string, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", false
	}

	parsed, err := url.Parse(raw)
	if err != nil {
		return "", false
	}
	if parsed.Scheme != "" {
		scheme := strings.ToLower(parsed.Scheme)
		if scheme != "http" && scheme != "https" {
			return "", false
		}
	}

	resolved := base.ResolveReference(parsed)
	resolved.Fragment = ""
	if resolved.Scheme != "http" && resolved.Scheme != "https" {
		return "", false
	}
	if c.sameHost && resolved.Host != allowedHost {
		return "", false
	}
	return resolved.String(), true
}

func (c *Crawler) extractLinks(base *url.URL, body []byte, allowedHost string) []string {
	matches := c.hrefRegex.FindAllSubmatch(body, -1)
	unique := make(map[string]struct{})
	for _, match := range matches {
		if len(match) < 2 {
			continue
		}
		if normalized, ok := c.normalizeLink(base, string(match[1]), allowedHost); ok {
			unique[normalized] = struct{}{}
		}
	}

	links := make([]string, 0, len(unique))
	for link := range unique {
		links = append(links, link)
	}
	sort.Strings(links)
	return links
}

func (c *Crawler) processJob(ctx context.Context, job crawlJob, allowedHost string, enqueue func(crawlJob)) PageResult {
	result := PageResult{URL: job.url, Depth: job.depth}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, job.url, nil)
	if err != nil {
		result.Error = err.Error()
		return result
	}

	resp, err := c.client.Do(req)
	if err != nil {
		result.Error = err.Error()
		return result
	}
	defer resp.Body.Close()

	result.StatusCode = resp.StatusCode
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		result.Error = err.Error()
		return result
	}

	contentType := resp.Header.Get("Content-Type")
	if strings.Contains(contentType, "text/html") && job.depth < c.maxDepth {
		baseURL, err := url.Parse(job.url)
		if err == nil {
			links := c.extractLinks(baseURL, body, allowedHost)
			result.LinksFound = len(links)
			for _, link := range links {
				enqueue(crawlJob{url: link, depth: job.depth + 1})
			}
		}
	}

	return result
}

func (c *Crawler) Crawl(ctx context.Context, seed string) []PageResult {
	seedURL, err := url.Parse(seed)
	if err != nil {
		return []PageResult{{URL: seed, Error: err.Error()}}
	}

	jobs := make(chan crawlJob, c.workers*2)
	resultsCh := make(chan PageResult, c.workers*2)

	var pending sync.WaitGroup
	var workersWG sync.WaitGroup

	enqueue := func(job crawlJob) {
		if job.depth > c.maxDepth {
			return
		}
		if !c.markVisited(job.url) {
			return
		}
		pending.Add(1)
		select {
		case jobs <- job:
		case <-ctx.Done():
			pending.Done()
		}
	}

	for i := 0; i < c.workers; i++ {
		workersWG.Add(1)
		go func() {
			defer workersWG.Done()
			for job := range jobs {
				result := c.processJob(ctx, job, seedURL.Host, enqueue)
				select {
				case resultsCh <- result:
				case <-ctx.Done():
				}
				pending.Done()
			}
		}()
	}

	enqueue(crawlJob{url: seedURL.String(), depth: 0})

	go func() {
		pending.Wait()
		close(jobs)
	}()
	go func() {
		workersWG.Wait()
		close(resultsCh)
	}()

	results := make([]PageResult, 0)
	for result := range resultsCh {
		results = append(results, result)
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].URL < results[j].URL
	})
	return results
}

func main() {
	startURL := flag.String("url", "https://example.com", "starting URL to crawl")
	depth := flag.Int("depth", 1, "maximum crawl depth")
	workers := flag.Int("workers", 4, "number of worker goroutines")
	timeout := flag.Duration("timeout", 10*time.Second, "overall request timeout")
	sameHost := flag.Bool("same-host", true, "only follow links on the same host")
	flag.Parse()

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	crawler := NewCrawler(*timeout, *workers, *depth, *sameHost)
	results := crawler.Crawl(ctx, *startURL)

	var failures int
	fmt.Printf("Crawl summary for %s\n", *startURL)
	fmt.Printf("workers=%d depth=%d same-host=%t timeout=%s\n\n", *workers, *depth, *sameHost, timeout.String())

	for _, result := range results {
		if result.Error != "" {
			failures++
			fmt.Printf("[ERROR] depth=%d url=%s err=%s\n", result.Depth, result.URL, result.Error)
			continue
		}
		fmt.Printf("[OK]    depth=%d status=%d links=%d url=%s\n", result.Depth, result.StatusCode, result.LinksFound, result.URL)
	}

	fmt.Println()
	fmt.Printf("visited=%d failures=%d\n", len(results), failures)
}
