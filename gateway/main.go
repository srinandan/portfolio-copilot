package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"golang.org/x/oauth2/google"
)

func main() {
	r := gin.Default()

	// Health check endpoint for Cloud Run
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "ok",
		})
	})

	// Setup ADC authentication simulation
	// In production, the gateway would use ADC to authenticate requests to the orchestrator.
	r.GET("/api/auth-check", func(c *gin.Context) {
		ctx := context.Background()
		// Try to find default credentials
		creds, err := google.FindDefaultCredentials(ctx, "https://www.googleapis.com/auth/cloud-platform")
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": fmt.Sprintf("Failed to find default credentials: %v", err),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"project_id": creds.ProjectID,
			"message":    "ADC is configured correctly.",
		})
	})

	// Server-Sent Events (SSE) streaming scaffold
	r.GET("/api/stream", func(c *gin.Context) {
		// Set headers for SSE
		c.Writer.Header().Set("Content-Type", "text/event-stream")
		c.Writer.Header().Set("Cache-Control", "no-cache")
		c.Writer.Header().Set("Connection", "keep-alive")

		// Flush headers
		c.Writer.Flush()

		// Simulate event streaming from orchestrator
		clientGone := c.Request.Context().Done()

		ticker := time.NewTicker(1 * time.Second)
		defer ticker.Stop()

		for i := 0; i < 5; i++ {
			select {
			case <-clientGone:
				log.Println("Client disconnected")
				return
			case t := <-ticker.C:
				// Write SSE format
				fmt.Fprintf(c.Writer, "event: message\n")
				fmt.Fprintf(c.Writer, "data: {\"time\": \"%s\", \"message\": \"Event %d\"}\n\n", t.Format(time.RFC3339), i)
				c.Writer.Flush()
			}
		}

		fmt.Fprintf(c.Writer, "event: close\n")
		fmt.Fprintf(c.Writer, "data: Stream finished\n\n")
		c.Writer.Flush()
	})

	// Run on port 8080 by default (Cloud Run default)
	r.Run(":8080")
}
