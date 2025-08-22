#!/usr/bin/env python3
"""Test script for OpenAI Reflection Service."""

import sys
from pathlib import Path

# Add the agentic_pipeline to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agentic_pipeline.services.openai_reflection_service import OpenAIReflectionService

def test_reflection_service():
    """Test the OpenAI reflection service with sample TDD data."""
    
    print("🚀 Testing OpenAI Reflection Service...")
    
    try:
        # Initialize the service (will use API key from settings.json)
        service = OpenAIReflectionService()
        print(f"✅ Service initialized successfully")
        print(f"📊 Using model: {service.model}")
        
        # Test connection
        print("\n🔗 Testing connection...")
        if service.test_connection():
            print("✅ Connection test passed")
        else:
            print("❌ Connection test failed")
            return
        
        # Sample test data
        sample_git_diff = """
diff --git a/src/services/LibraryCacheService.ts b/src/services/LibraryCacheService.ts
index 1234567..abcdefg 100644
--- a/src/services/LibraryCacheService.ts
+++ b/src/services/LibraryCacheService.ts
@@ -45,6 +45,18 @@ export class LibraryCacheService {
     return this.cachedDocuments;
   }
   
+  /**
+   * Get a specific document by ID from cache
+   */
+  async getCachedDocumentById(documentId: string): Promise<TranscriptFile | null> {
+    const cachedIds = await this.getCachedDocumentIds();
+    
+    if (!cachedIds.includes(documentId)) {
+      return null;
+    }
+    
+    return await this.storage.getItem(`document_${documentId}`);
+  }
+  
   private async getCachedDocumentIds(): Promise<string[]> {
     const metadata = await this.storage.getItem(this.CACHE_METADATA_KEY);
     return metadata?.cachedDocumentIds || [];

diff --git a/src/__tests__/unit/services/LibraryCacheService/GetDocumentById.test.ts b/src/__tests__/unit/services/LibraryCacheService/GetDocumentById.test.ts
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/__tests__/unit/services/LibraryCacheService/GetDocumentById.test.ts
@@ -0,0 +1,25 @@
+import { LibraryCacheService } from "../../../../services/LibraryCacheService";
+
+describe("LibraryCacheService - getCachedDocumentById", () => {
+  let cacheService: LibraryCacheService;
+
+  beforeEach(() => {
+    cacheService = new LibraryCacheService();
+  });
+
+  it("should return null when document not in cache", async () => {
+    const result = await cacheService.getCachedDocumentById("nonexistent-doc");
+    expect(result).toBeNull();
+  });
+
+  it("should return cached document when it exists", async () => {
+    const testDoc = { uniqueId: "test-doc", title: "Test Document" };
+    await cacheService.cacheFullDocument(testDoc);
+    
+    const result = await cacheService.getCachedDocumentById("test-doc");
+    expect(result).not.toBeNull();
+    expect(result?.uniqueId).toBe("test-doc");
+  });
+});
"""
        
        sample_task_details = {
            "id": "123",
            "title": "Test: getCachedDocumentById should return cached document when it exists",
            "description": "Validate that the cache service can retrieve individual documents by ID",
            "acceptance_criteria": """
Given: A document is cached in the service
When: getCachedDocumentById is called with the document's ID  
Then: The cached document should be returned
And: The returned document should have the correct uniqueId

Given: A document ID that doesn't exist in cache
When: getCachedDocumentById is called with that ID
Then: null should be returned
"""
        }
        
        sample_bdd_scenarios = sample_task_details["acceptance_criteria"]
        
        print("\n🤔 Running reflection analysis...")
        print("📝 Sample git diff preview:")
        print(sample_git_diff[:200] + "..." if len(sample_git_diff) > 200 else sample_git_diff)
        
        # Call the reflection service
        result = service.evaluate_tdd_implementation(
            git_diff=sample_git_diff,
            task_details=sample_task_details,
            bdd_scenarios=sample_bdd_scenarios,
            iteration_context="TDD iteration 1/3 - Testing getCachedDocumentById functionality"
        )
        
        print(f"\n📊 REFLECTION RESULT:")
        print(f"Status: {result.status}")
        print(f"Feedback: {result.feedback}")
        
        if result.status == "continue":
            print("✅ Reflection approved - implementation ready to advance")
        elif result.status == "retry":
            print("🔄 Reflection requested retry - improvements needed")
        
        print(f"\n🎉 Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_reflection_service()