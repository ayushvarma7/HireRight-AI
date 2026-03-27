"""
Supabase Vector Service

Vector database operations for job storage and similarity search using Supabase pgvector.
"""

from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.services.embedding import get_embedding
from app.db.database import get_supabase

class SupabaseVectorService:
    """Service for Supabase vector database operations using pgvector."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.table_name = "jobs"
    
    async def upsert_job(
        self,
        job_id: str,
        job_text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Upsert a job listing into Supabase with its embedding.
        """
        # Generate embedding
        embedding = await get_embedding(job_text)
        
        # Build upsert data
        upsert_data = {
            "id": job_id,
            "embedding": embedding,
            **metadata
        }
        
        # Upsert to Supabase
        self.supabase.table(self.table_name).upsert(upsert_data).execute()
    
    async def upsert_jobs_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> int:
        """
        Batch upsert multiple jobs.
        """
        from app.services.embedding import get_embeddings
        
        # Generate all embeddings
        texts = [job["text"] for job in jobs]
        embeddings = await get_embeddings(texts)
        
        # Build upsert data list
        upsert_data_list = []
        for i, job in enumerate(jobs):
            data = {
                "id": job["id"],
                "embedding": embeddings[i],
                **job["metadata"]
            }
            upsert_data_list.append(data)
        
        # Upsert to Supabase
        self.supabase.table(self.table_name).upsert(upsert_data_list).execute()
        
        return len(jobs)
    
    async def search_jobs(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar jobs using pgvector match_documents RPC.
        
        Note: Requires 'match_jobs' RPC to be defined in Supabase.
        """
        # Generate query embedding
        query_embedding = await get_embedding(query)
        
        # Call match_jobs RPC
        rpc_params = {
            "query_embedding": query_embedding,
            "match_threshold": 0.55,  # snippet-based embeddings peak at ~0.65; 0.55 filters noise while returning real matches
            "match_count": top_k,
        }
        
        # Add filtering if needed (Supabase RPC can take filter params)
        if filter:
            # This depends on how the RPC is defined. 
            # For simplicity, we'll assume the RPC handles basic filtering or we filter post-RPC.
            rpc_params.update(filter)
        
        response = self.supabase.rpc("match_jobs", rpc_params).execute()
        
        # Format results
        jobs = []
        for match in response.data:
            jobs.append({
                "id": match["id"],
                "score": match["similarity"],
                **match # Include all other metadata fields
            })
        
        return jobs
    
    async def delete_job(self, job_id: str) -> None:
        """Delete a job from the database."""
        self.supabase.table(self.table_name).delete().eq("id", job_id).execute()

# Singleton instance
_vector_service: Optional[SupabaseVectorService] = None

def get_vector_service() -> SupabaseVectorService:
    """Get or create Supabase Vector service instance."""
    global _vector_service
    if _vector_service is None:
        _vector_service = SupabaseVectorService()
    return _vector_service
