package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"sync"
	"time"
)

type Store interface {
	Set(key, value string)
	Get(key string) (string, bool)
	Delete(key string) bool
	List() map[string]string
	Save() error
	Load() error
	Close() error
}

type PersistentStore struct {
	mu               sync.RWMutex
	data             map[string]string
	filePath         string
	autosaveInterval time.Duration
	dirty            chan struct{}
	stop             chan struct{}
	done             chan struct{}
}

func NewPersistentStore(filePath string, autosaveInterval time.Duration) (*PersistentStore, error) {
	store := &PersistentStore{
		data:             make(map[string]string),
		filePath:         filePath,
		autosaveInterval: autosaveInterval,
		dirty:            make(chan struct{}, 1),
		stop:             make(chan struct{}),
		done:             make(chan struct{}),
	}

	if err := store.Load(); err != nil {
		return nil, err
	}

	go store.backgroundSync()
	return store, nil
}

func (s *PersistentStore) Set(key, value string) {
	s.mu.Lock()
	s.data[key] = value
	s.mu.Unlock()
	s.markDirty()
}

func (s *PersistentStore) Get(key string) (string, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	value, ok := s.data[key]
	return value, ok
}

func (s *PersistentStore) Delete(key string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.data[key]; !ok {
		return false
	}
	delete(s.data, key)
	s.markDirty()
	return true
}

func (s *PersistentStore) List() map[string]string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	copyOfData := make(map[string]string, len(s.data))
	for key, value := range s.data {
		copyOfData[key] = value
	}
	return copyOfData
}

func (s *PersistentStore) Save() error {
	snapshot := s.List()
	payload, err := json.MarshalIndent(snapshot, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.filePath, append(payload, '\n'), 0o644)
}

func (s *PersistentStore) Load() error {
	payload, err := os.ReadFile(s.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	if len(strings.TrimSpace(string(payload))) == 0 {
		return nil
	}

	loaded := make(map[string]string)
	if err := json.Unmarshal(payload, &loaded); err != nil {
		return err
	}

	s.mu.Lock()
	s.data = loaded
	s.mu.Unlock()
	return nil
}

func (s *PersistentStore) markDirty() {
	select {
	case s.dirty <- struct{}{}:
	default:
	}
}

func (s *PersistentStore) backgroundSync() {
	defer close(s.done)
	ticker := time.NewTicker(s.autosaveInterval)
	defer ticker.Stop()

	dirty := false
	for {
		select {
		case <-s.dirty:
			dirty = true
		case <-ticker.C:
			if dirty {
				if err := s.Save(); err != nil {
					log.Printf("autosave failed: %v", err)
				} else {
					dirty = false
				}
			}
		case <-s.stop:
			if dirty {
				if err := s.Save(); err != nil {
					log.Printf("final save failed: %v", err)
				}
			}
			return
		}
	}
}

func (s *PersistentStore) Close() error {
	close(s.stop)
	<-s.done
	return nil
}

func handleCommand(store Store, line string) (bool, error) {
	line = strings.TrimSpace(line)
	if line == "" {
		return true, nil
	}

	parts := strings.Fields(line)
	command := strings.ToLower(parts[0])

	switch command {
	case "help":
		fmt.Println("Commands: set <key> <value>, get <key>, delete <key>, list, save, help, exit")
	case "set":
		segments := strings.SplitN(line, " ", 3)
		if len(segments) < 3 {
			return true, fmt.Errorf("usage: set <key> <value>")
		}
		key := strings.TrimSpace(segments[1])
		value := strings.TrimSpace(segments[2])
		if key == "" {
			return true, fmt.Errorf("key cannot be empty")
		}
		store.Set(key, value)
		fmt.Printf("stored %q\n", key)
	case "get":
		if len(parts) != 2 {
			return true, fmt.Errorf("usage: get <key>")
		}
		value, ok := store.Get(parts[1])
		if !ok {
			fmt.Printf("%q not found\n", parts[1])
			return true, nil
		}
		fmt.Printf("%s = %s\n", parts[1], value)
	case "delete":
		if len(parts) != 2 {
			return true, fmt.Errorf("usage: delete <key>")
		}
		if store.Delete(parts[1]) {
			fmt.Printf("deleted %q\n", parts[1])
		} else {
			fmt.Printf("%q not found\n", parts[1])
		}
	case "list":
		items := store.List()
		if len(items) == 0 {
			fmt.Println("store is empty")
			return true, nil
		}
		keys := make([]string, 0, len(items))
		for key := range items {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			fmt.Printf("%s = %s\n", key, items[key])
		}
	case "save":
		if err := store.Save(); err != nil {
			return true, err
		}
		fmt.Println("store saved")
	case "exit", "quit":
		return false, nil
	default:
		return true, fmt.Errorf("unknown command %q", command)
	}

	return true, nil
}

func runCLI(store Store) error {
	scanner := bufio.NewScanner(os.Stdin)
	fmt.Println("Key-Value Store")
	fmt.Println("Type 'help' for commands.")

	for {
		fmt.Print("> ")
		if !scanner.Scan() {
			fmt.Println()
			return scanner.Err()
		}

		keepRunning, err := handleCommand(store, scanner.Text())
		if err != nil {
			fmt.Printf("error: %v\n", err)
			continue
		}
		if !keepRunning {
			return nil
		}
	}
}

func main() {
	filePath := flag.String("file", "store.json", "path to the persistence file")
	autosave := flag.Duration("autosave", 5*time.Second, "autosave interval")
	flag.Parse()

	store, err := NewPersistentStore(*filePath, *autosave)
	if err != nil {
		log.Fatalf("failed to create store: %v", err)
	}
	defer func() {
		if err := store.Close(); err != nil {
			log.Printf("failed to close store: %v", err)
		}
	}()

	if err := runCLI(store); err != nil {
		log.Fatalf("cli error: %v", err)
	}
}
