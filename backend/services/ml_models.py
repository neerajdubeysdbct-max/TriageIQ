"""
ML Models Service
Handles BERT clustering, XGBoost scoring, LSTM forecasting
"""

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os
from datetime import datetime

class BERTClusteringModel:
    """
    BERT-based semantic clustering for ticket descriptions
    """
    def __init__(self):
        self.model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
        self.model = None
        self.clusterer = None
        
    def load_model(self):
        """Load the sentence-transformer once; later calls reuse it."""
        if self.model is None:
            print(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
        return self
    
    def encode_descriptions(self, descriptions):
        """
        Convert ticket descriptions to embeddings
        
        Args:
            descriptions: List of ticket description strings
            
        Returns:
            numpy array of embeddings (n_tickets, 384)
        """
        if self.model is None:
            self.load_model()
        
        # Encode in batches for efficiency
        embeddings = self.model.encode(
            descriptions,
            batch_size=256,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def cluster_tickets(self, embeddings, min_cluster_size=50, method='kmeans', n_clusters=20):
        """
        Cluster tickets using KMeans (all assigned) or HDBSCAN (with noise)
        
        Args:
            embeddings: BERT embeddings
            min_cluster_size: For HDBSCAN
            method: 'kmeans' (all tickets) or 'hdbscan' (allows noise)
            n_clusters: Number of clusters for KMeans
            
        Returns:
            cluster_labels, cluster_probabilities
        """
        print(f"Clustering {len(embeddings)} tickets using {method.upper()}...")
        
        if method == 'kmeans':
            from sklearn.cluster import KMeans
            
            # Auto-determine clusters if needed (rule of thumb: sqrt(n/2))
            if n_clusters is None:
                n_clusters = min(max(int((len(embeddings) / 2) ** 0.5), 10), 50)
            
            self.clusterer = KMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=10
            )
            cluster_labels = self.clusterer.fit_predict(embeddings)
            
            # Calculate pseudo-probabilities based on distance to centroid
            distances = self.clusterer.transform(embeddings)
            min_distances = distances.min(axis=1)
            max_dist = min_distances.max() if min_distances.max() > 0 else 1
            probabilities = 1 - (min_distances / max_dist)
            
        else:  # hdbscan
            from sklearn.cluster import HDBSCAN
            
            self.clusterer = HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=10,
                metric='euclidean',
                cluster_selection_method='eom'
            )
            cluster_labels = self.clusterer.fit_predict(embeddings)
            probabilities = self.clusterer.probabilities_
        
        n_clusters_found = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        noise_count = sum(1 for l in cluster_labels if l == -1)
        print(f"✓ Found {n_clusters_found} clusters, {noise_count} noise points")
        
        return cluster_labels, probabilities
    
   
    def get_cluster_summary(self, descriptions, cluster_labels):
        """
        Get representative samples and statistics from each cluster
        
        Returns:
            dict: {cluster_id: {'count': X, 'samples': [...], 'top_words': [...]}}
        """
        import pandas as pd
        from collections import Counter
        
        df = pd.DataFrame({
            'description': descriptions,
            'cluster': cluster_labels
        })
        
        cluster_summary = {}
        
        for cluster_id in df['cluster'].unique():
            if cluster_id == -1:  # Skip noise
                noise_count = len(df[df['cluster'] == -1])
                cluster_summary[-1] = {
                    'count': noise_count,
                    'samples': df[df['cluster'] == -1]['description'].head(10).tolist(),
                    'top_words': []
                }
                continue
            
            cluster_docs = df[df['cluster'] == cluster_id]['description'].tolist()
            
            # Get diverse samples (not just first 5)
            unique_samples = list(set(cluster_docs))[:10]  # Up to 10 unique samples
            
            # Get top words in this cluster
            all_text = ' '.join(cluster_docs).lower()
            words = [w for w in all_text.split() if len(w) > 3]  # Words > 3 chars
            top_words = [word for word, count in Counter(words).most_common(10)]
            
            cluster_summary[int(cluster_id)] = {
                'count': len(cluster_docs),
                'samples': unique_samples,
                'top_words': top_words
            }
        
        return cluster_summary
            


class XGBoostScoringModel:
    """
    XGBoost model for automation potential scoring
    """
    def __init__(self):
        self.model = None
        self.feature_names = [
            'mttr_hours',
            'reassignment_count',
            'reopen_count',
            'description_length',
            'resolution_length',
            'is_portal',
            'is_email',
            'is_phone',
            'hour_of_day',
            'day_of_week',
            'cluster_size',
            'cluster_similarity',
            'has_resolution_code',
            'mttr_variance',
            'repeatability_score'
        ]
    
    def load_model(self, model_path='models/xgboost_automation_scorer.pkl'):
        """Load trained XGBoost model"""
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            print(f"Loaded XGBoost model from {model_path}")
        else:
            print(f"Model not found at {model_path}, using rule-based scoring")
            self.model = None
        return self
    
    def extract_features(self, tickets_df, cluster_info):
        """
        Extract features for automation scoring
        
        Args:
            tickets_df: DataFrame with ticket data
            cluster_info: Dict with cluster statistics
            
        Returns:
            numpy array of features
        """
        features = []
        
        for _, ticket in tickets_df.iterrows():
            feature_vector = [
                ticket.get('mttr_hours', 0) or 0,
                ticket.get('reassignment_count', 0) or 0,
                ticket.get('reopen_count', 0) or 0,
                len(str(ticket.get('short_description', ''))),
                len(str(ticket.get('resolution_notes', ''))),
                1 if ticket.get('contact_type', '').lower() == 'portal' else 0,
                1 if ticket.get('contact_type', '').lower() == 'email' else 0,
                1 if ticket.get('contact_type', '').lower() == 'phone' else 0,
                pd.to_datetime(ticket.get('opened')).hour if pd.notna(ticket.get('opened')) else 12,
                pd.to_datetime(ticket.get('opened')).dayofweek if pd.notna(ticket.get('opened')) else 3,
                cluster_info.get(ticket.get('cluster_id', -1), {}).get('size', 0),
                ticket.get('cluster_similarity', 0) or 0,
                1 if pd.notna(ticket.get('resolution_notes')) else 0,
                cluster_info.get(ticket.get('cluster_id', -1), {}).get('mttr_variance', 0),
                cluster_info.get(ticket.get('cluster_id', -1), {}).get('repeatability', 0)
            ]
            features.append(feature_vector)
        
        return np.array(features)
    
    def predict_automation_score(self, features):
        """
        Predict automation potential (0-100)
        
        Returns:
            array of scores
        """
        if self.model is not None:
            # Use trained model
            scores = self.model.predict_proba(features)[:, 1] * 100
        else:
            # Rule-based scoring
            scores = self._rule_based_scoring(features)
        
        return scores
    
    def _rule_based_scoring(self, features):
        """
        Simple rule-based scoring if model not available
        """
        scores = []
        
        for feature_vec in features:
            score = 50  # Base score
            
            # Low MTTR = higher automation potential
            if feature_vec[0] < 1:  # < 1 hour
                score += 20
            elif feature_vec[0] < 4:
                score += 10
            
            # No reassignments = higher potential
            if feature_vec[1] == 0:
                score += 10
            
            # No reopens = higher potential
            if feature_vec[2] == 0:
                score += 10
            
            # Portal submission = higher potential
            if feature_vec[5] == 1:
                score += 10
            
            scores.append(min(score, 100))
        
        return np.array(scores)


class AutomationDetector:
    """
    Detects if tickets are already automated or can be automated
    """
    
  
    @staticmethod
    def is_already_automated(ticket, xgboost_confidence=None):
        """
        3-Layer automation detection:
          Layer 1: Hard rules (100% certain cases)
          Layer 2: ML-assisted (grey zone — XGBoost decides)
          Layer 3: Heuristic fallback (no model available)
        
        Works for any ITSM export format
        No dependency on pre-tagged fields like aiops_*.
        """
        
        # --- FLEXIBLE FIELD EXTRACTION ---
        resolved_by = str(
            ticket.get('resolved_by') or 
            ticket.get('Resolved by') or ''
        ).strip().lower()
        
        assign_group = str(
            ticket.get('assignment_group') or 
            ticket.get('Assignment group') or ''
        ).strip().lower()
        
        resolved_group = str(
            ticket.get('resolved_by_group') or 
            ticket.get('Resolved by group') or ''
        ).strip().lower()
        
        sys_updated = str(
            ticket.get('sys_updated_by') or ''
        ).strip().lower()
        
        assigned_to = str(
            ticket.get('assigned_to') or 
            ticket.get('Assigned to') or ''
        ).strip().lower()
        
        # MTTR: handle hours or minutes
        mttr = None
        for field in ['mttr_hours', 'Resolve time', 'resolve_time', 
                      'resolution_time', 'time_to_resolve']:
            val = ticket.get(field)
            if val is not None:
                try:
                    mttr = float(val)
                    if mttr > 100:  # likely minutes, convert to hours
                        mttr = mttr / 60
                    break
                except (ValueError, TypeError):
                    continue
        if mttr is None:
            mttr = 999
        
        channel = str(
            ticket.get('channel') or 
            ticket.get('Channel') or 
            ticket.get('contact_type') or ''
        ).strip().lower()
        
        resolution_code = str(
            ticket.get('resolution_code') or 
            ticket.get('Resolution code') or ''
        ).strip().lower()
        
        state = str(
            ticket.get('state') or 
            ticket.get('State') or ''
        ).strip().lower()
        
        resolution_notes = str(
            ticket.get('resolution_notes') or 
            ticket.get('Resolution notes') or ''
        ).strip().lower()
        
        reassign = 0
        for field in ['reassignment_count', 'reassignments', 'Reassignment count']:
            val = ticket.get(field)
            if val is not None:
                try:
                    reassign = int(float(val))
                    break
                except (ValueError, TypeError):
                    continue
        
        desc = str(ticket.get('short_description', '') or '').lower()
        
        # --- DETECT: System or Human? ---
        system_ids = [
            'system', 'auto', 'bot', 'netcool', 'svc_', 'api',
            'scheduled', 'orchestrat', 'ignio', 'integration',
            'cron', 'daemon', 'batch', 'script', 'monitor',
            'noreply', 'service-now', 'servicenow', 'workflow'
        ]
        
        
        is_empty_resolver = not resolved_by or resolved_by in ['nan', 'none', '']
        
        is_system = (
            any(s in resolved_by for s in system_ids) or
            any(s in assigned_to for s in system_ids)
        )
        # sys_updated_by is often 'system' in ServiceNow (platform default)
        # Only use it if resolved_by is empty
        if is_empty_resolver and any(s in sys_updated for s in system_ids):
            is_system = True
        is_empty_resolver = not resolved_by or resolved_by in ['nan', 'none', '']
        
        # Human = has space (first+last name) AND not a system identifier
        # Also check: if resolved_by matches assignment_group, it's a queue not a person
        is_queue = resolved_by and (
            resolved_by in assign_group or 
            assign_group in resolved_by
        ) and len(resolved_by) > 5
        
        is_human = (
            ' ' in resolved_by and
            not is_system and
            not is_empty_resolver and
            not is_queue
        )
        
        # --- DETECT: Automation team? ---
        auto_teams = [
            'automation', 'netcool', 'auto-', 'ignio', 'self-heal',
            'orchestrat', 'bot', 'automat', 'monitoring', 'event mgmt'
        ]
        is_auto_team = (
            any(t in assign_group for t in auto_teams) or
            any(t in resolved_group for t in auto_teams)
        )
        
        # --- DETECT: Resolution notes suggest automation? ---
        auto_resolution = any(w in resolution_notes for w in [
            'auto', 'automated', 'script ran', 'bot resolved', 
            'auto-resolved', 'automatically', 'runbook executed'
        ])
        
        # ==========================================
        # LAYER 1: HARD RULES (100% certain)
        # ==========================================
        
        # Cancelled/invalid tickets = NOT automated
        if 'cancel' in resolution_code or 'cancel' in state:
            return False
        
        # System resolved + automation team = AUTOMATED
        if is_system and is_auto_team:
            return True
        
        # System resolved + fast (< 1 hour) = AUTOMATED
        if is_system and mttr < 1:
            return True
        
        # Human resolved + slow (> 10 min) = NOT automated
        if is_human and mttr > 0.17:
            return False
        
        # Human resolved + multiple reassignments = NOT automated
        if is_human and reassign >= 2:
            return False
        
        # ==========================================
        # LAYER 2: GREY ZONE — ML decides (if available)
        # ==========================================
        # Grey zone: not clearly system, not clearly human+slow
        # Examples: human name + fast, empty resolver, auto team + slow
        
        if xgboost_confidence is not None:
            # Very high ML confidence + supporting evidence
            if xgboost_confidence >= 0.95 and mttr < 0.5 and not is_human:
                return True
            
            # High ML confidence + automation team
            if xgboost_confidence >= 0.90 and is_auto_team and not is_human:
                return True
            
            # High ML confidence + auto resolution notes
            if xgboost_confidence >= 0.90 and auto_resolution:
                return True
            
            # ML says clearly manual
            if xgboost_confidence < 0.40:
                return False
            
            # ML uncertain + human resolved = NOT automated (conservative)
            if is_human:
                return False
            
            # ML moderately confident + fast + zero reassign
            if xgboost_confidence >= 0.70 and mttr < 0.5 and reassign == 0:
                return True
            
            return False
        
        # ==========================================
        # LAYER 3: HEURISTIC FALLBACK (no model yet)
        # ==========================================
        
        # Machine speed (< 3 min) + zero reassignment
        if mttr < 0.05 and reassign == 0 and not is_human:
            return True
        
        # Automation team + fast + zero reassignment
        if is_auto_team and mttr < 0.5 and reassign == 0 and not is_human:
            return True
        
        # Event/monitoring channel + auto team + fast
        if ('event' in channel or 'monitor' in channel):
            if is_auto_team and mttr < 1:
                return True
        
        # Auto resolution notes + fast
        if auto_resolution and mttr < 1:
            return True
        
        # Human resolved (catch-all) = NOT automated
        if is_human:
            return False
        
        # Everything else = NOT automated (conservative)
        return False

            
    @staticmethod
    def can_be_automated(automation_score, cluster_size):
        """
        Determine if ticket can be automated based on score and cluster
        
        Args:
            automation_score: 0-100 score
            cluster_size: Number of similar tickets
            
        Returns:
            str: 'High', 'Medium', 'Low', 'Not Feasible'
        """
        if automation_score >= 80 and cluster_size >= 50:
            return 'High'
        elif automation_score >= 60 and cluster_size >= 20:
            return 'Medium'
        elif automation_score >= 40:
            return 'Low'
        else:
            return 'Not Feasible'


class MultiTaskCategorizer:
    """
    Multi-task model for L1/L2/L3/L4 categorization
    Uses BERT embeddings + classification heads
    """
    
    def __init__(self):
        self.bert_model = None
        self.l1_model = None
        self.l2_model = None
        
        # Predefined categories (can be learned from data)
        self.l1_categories = [
            'Network', 'Server', 'Application', 'Database', 
            'Security', 'Hardware', 'Cloud', 'Email'
        ]
        
        self.l2_map = {
            'Network': ['VPN Access', 'Port Down', 'Switch Issue', 'DNS', 'DHCP'],
            'Server': ['Memory Issue', 'CPU High', 'Disk Space', 'Service Down'],
            'Application': ['Login Issue', 'Slow Performance', 'Crash', 'Feature Request'],
            'Security': ['Password Reset', 'Account Unlock', 'Access Request', 'MFA Issue'],
            'Hardware': ['Printer', 'Monitor', 'Keyboard', 'Mouse', 'Laptop'],
            'Email': ['Outlook Sync', 'Cannot Send', 'Storage Full', 'Spam']
        }
    
    def load_models(self):
        """Load BERT and classification models"""
        self.bert_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        # L1/L2 models would be loaded here if trained
        # For now, use semantic similarity
        return self
    
    def predict_categories(self, description):
        """
        Predict all 4 levels for a ticket description
        
        Returns:
            dict with predictions and confidences
        """
        if self.bert_model is None:
            self.load_models()
        
        # The rules below don't use an embedding; encoding every ticket one by
        # one here only cost time, so it is skipped.
        embedding = None
        
        # Predict L1 (using similarity to category keywords)
        l1_pred, l1_conf = self._predict_l1(description, embedding)
        
        # Predict L2 (based on L1)
        l2_pred, l2_conf = self._predict_l2(description, l1_pred, embedding)
        
        # Predict L3 (automation feasibility)
        l3_pred, l3_conf = self._predict_l3(description)
        
        # Predict L4 (automation type)
        l4_pred, l4_conf = self._predict_l4(description, l3_pred)
        
        return {
            'l1_category': l1_pred,
            'l1_confidence': l1_conf,
            'l2_subcategory': l2_pred,
            'l2_confidence': l2_conf,
            'l3_automation_feasibility': l3_pred,
            'l3_confidence': l3_conf,
            'l4_automation_type': l4_pred,
            'l4_confidence': l4_conf
        }
    
    def _predict_l1(self, description, embedding):
        """Predict L1 category using keyword matching and similarity"""
        desc_lower = description.lower()
        
        # Keyword-based prediction
        if any(word in desc_lower for word in ['vpn', 'network', 'connection', 'switch', 'port']):
            return 'Network', 0.92
        elif any(word in desc_lower for word in ['password', 'pwd', 'login', 'access', 'unlock']):
            return 'Security', 0.88
        elif any(word in desc_lower for word in ['server', 'memory', 'cpu', 'disk', 'service']):
            return 'Server', 0.85
        elif any(word in desc_lower for word in ['outlook', 'email', 'mail', 'inbox']):
            return 'Email', 0.90
        elif any(word in desc_lower for word in ['sap', 'application', 'software', 'app']):
            return 'Application', 0.80
        else:
            return 'Application', 0.65  # Default with lower confidence
    
    def _predict_l2(self, description, l1_category, embedding):
        """Predict L2 subcategory based on L1"""
        desc_lower = description.lower()
        
        if l1_category not in self.l2_map:
            return 'Other', 0.50
        
        possible_l2 = self.l2_map[l1_category]
        
        # Simple keyword matching
        for l2_cat in possible_l2:
            if any(word in desc_lower for word in l2_cat.lower().split()):
                return l2_cat, 0.85
        
        return possible_l2[0], 0.60  # Default to first option
    
    def _predict_l3(self, description):
        """Predict automation feasibility"""
        desc_lower = description.lower()
        
        # High automation potential keywords
        high_keywords = ['password', 'reset', 'unlock', 'vpn', 'access']
        # Low automation keywords
        low_keywords = ['complex', 'custom', 'investigate', 'troubleshoot']
        
        high_count = sum(1 for word in high_keywords if word in desc_lower)
        low_count = sum(1 for word in low_keywords if word in desc_lower)
        
        if high_count >= 2:
            return 'High', 0.85
        elif low_count >= 1:
            return 'Low', 0.75
        else:
            return 'Medium', 0.70
    
    def _predict_l4(self, description, l3_feasibility):
        """Predict automation type"""
        if l3_feasibility == 'High':
            return 'Chatbot', 0.80
        elif l3_feasibility == 'Medium':
            return 'RPA', 0.75
        elif l3_feasibility == 'Low':
            return 'Self-Service Portal', 0.70
        else:
            return 'Manual', 0.90


# Singleton instances
bert_clustering = BERTClusteringModel()
xgboost_scorer = XGBoostScoringModel()
automation_detector = AutomationDetector()
multi_task_categorizer = MultiTaskCategorizer()

import matplotlib
matplotlib.use('Agg')  # For server without display
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
import seaborn as sns

def visualize_clusters(embeddings, cluster_labels, descriptions=None, output_path='cluster_plot.png'):
    """Visualize clusters in 2D with labels"""
    print("Reducing dimensions with t-SNE...")
    
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    embeddings_2d = tsne.fit_transform(embeddings)
    
    plt.figure(figsize=(16, 10))
    
    unique_clusters = set(cluster_labels)
    n_clusters = len(unique_clusters) - (1 if -1 in unique_clusters else 0)
    
    colors = sns.color_palette("hsv", n_clusters + 1)
    
    # Calculate cluster centers for labels
    from collections import Counter
    cluster_counts = Counter(cluster_labels)
    cluster_centers = {}
    
    for cluster_id in unique_clusters:
        mask = cluster_labels == cluster_id
        
        if cluster_id == -1:
            plt.scatter(embeddings_2d[mask, 0], embeddings_2d[mask, 1],
                       c='gray', label=f'Noise ({cluster_counts[cluster_id]})', 
                       alpha=0.3, s=20)
        else:
            plt.scatter(embeddings_2d[mask, 0], embeddings_2d[mask, 1],
                       c=[colors[cluster_id]], 
                       label=f'C{cluster_id} ({cluster_counts[cluster_id]})',
                       alpha=0.6, s=50)
            
            # Calculate center for annotation
            center_x = embeddings_2d[mask, 0].mean()
            center_y = embeddings_2d[mask, 1].mean()
            cluster_centers[cluster_id] = (center_x, center_y)
    
    # Add cluster number annotations at centers
    for cluster_id, (cx, cy) in cluster_centers.items():
        plt.annotate(f'{cluster_id}\n({cluster_counts[cluster_id]})', 
                    xy=(cx, cy),
                    fontsize=10,
                    fontweight='bold',
                    ha='center',
                    bbox=dict(boxstyle='round,pad=0.3', 
                            facecolor='white', 
                            edgecolor='black',
                            alpha=0.7))
    
    plt.title(f'BERT Clustering ({n_clusters} clusters, {len(embeddings)} tickets)', 
             fontsize=16, fontweight='bold')
    plt.xlabel('t-SNE Dimension 1', fontsize=12)
    plt.ylabel('t-SNE Dimension 2', fontsize=12)
    
    # Move legend outside to avoid overlap
    plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', ncol=2, fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")
    

def visualize_xgboost_features(feature_importance, feature_names, output_path='xgboost_features.png'):
    """
    Visualize XGBoost feature importance
    Shows which features matter most for automation scoring
    """
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Sort by importance
    indices = np.argsort(feature_importance)[::-1][:15]  # Top 15
    
    plt.figure(figsize=(10, 8))
    plt.barh(range(len(indices)), feature_importance[indices], color='steelblue')
    plt.yticks(range(len(indices)), [feature_names[i] for i in indices])
    plt.xlabel('Mean |SHAP value|', fontsize=12)
    plt.title('XGBoost Feature Importance (SHAP)\n(What Drives Automation Status?)', fontsize=14, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved XGBoost features: {output_path}")


def visualize_automation_distribution(automation_scores, output_path='automation_distribution.png'):
    """
    Visualize automation score distribution
    Shows how many tickets in each automation category
    """
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Categorize scores
    high = np.sum((automation_scores >= 80) & (automation_scores <= 100))
    medium = np.sum((automation_scores >= 50) & (automation_scores < 80))
    low = np.sum((automation_scores >= 20) & (automation_scores < 50))
    not_feasible = np.sum(automation_scores < 20)
    
    categories = ['High\n(80-100)', 'Medium\n(50-79)', 'Low\n(20-49)', 'Not Feasible\n(<20)']
    counts = [high, medium, low, not_feasible]
    colors = ['#2ecc71', '#f39c12', '#e67e22', '#e74c3c']
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Bar chart
    ax1.bar(categories, counts, color=colors, alpha=0.8)
    ax1.set_ylabel('Number of Tickets', fontsize=12)
    ax1.set_title('Automation Potential Distribution', fontsize=14, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    # Add count labels
    for i, (cat, count) in enumerate(zip(categories, counts)):
        ax1.text(i, count + max(counts)*0.02, f'{count:,}', ha='center', fontweight='bold')
    
    # Pie chart
    ax2.pie(counts, labels=categories, colors=colors, autopct='%1.1f%%', startangle=90)
    ax2.set_title('Percentage Breakdown', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved automation distribution: {output_path}")


def visualize_category_breakdown(tickets_df, output_path='category_breakdown.png'):
    """
    Visualize L1 category distribution
    Shows which categories have most tickets
    """
    import matplotlib.pyplot as plt
    
    # Count by L1 category
    category_counts = tickets_df['l1_category'].value_counts().head(10)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Horizontal bar chart
    colors_bar = plt.cm.Set3(range(len(category_counts)))
    ax1.barh(range(len(category_counts)), category_counts.values, color=colors_bar)
    ax1.set_yticks(range(len(category_counts)))
    ax1.set_yticklabels(category_counts.index)
    ax1.set_xlabel('Number of Tickets', fontsize=12)
    ax1.set_title('Top 10 L1 Categories', fontsize=14, fontweight='bold')
    ax1.invert_yaxis()
    
    # Add count labels
    for i, count in enumerate(category_counts.values):
        ax1.text(count + max(category_counts.values)*0.01, i, f'{count:,}', va='center')
    
    # Pie chart
    ax2.pie(category_counts.values, labels=category_counts.index, autopct='%1.1f%%', 
            colors=colors_bar, startangle=90)
    ax2.set_title('Category Distribution %', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved category breakdown: {output_path}")


def visualize_automation_by_category(tickets_df, output_path='automation_by_category.png'):
    """
    Visualize automation potential by category
    Shows which categories are easiest to automate
    """
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Group by category and calculate avg automation score
    category_automation = tickets_df.groupby('l1_category')['automation_potential_score'].agg(['mean', 'count'])
    category_automation = category_automation[category_automation['count'] >= 50]  # Min 50 tickets
    category_automation = category_automation.sort_values('mean', ascending=False).head(10)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Color bars by score
    colors = ['#2ecc71' if score >= 70 else '#f39c12' if score >= 50 else '#e74c3c' 
              for score in category_automation['mean']]
    
    bars = ax.barh(range(len(category_automation)), category_automation['mean'], color=colors, alpha=0.8)
    ax.set_yticks(range(len(category_automation)))
    ax.set_yticklabels(category_automation.index)
    ax.set_xlabel('Average Automation Score', fontsize=12)
    ax.set_title('Automation Potential by Category\n(Higher = Easier to Automate)', 
                 fontsize=14, fontweight='bold')
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3)
    
    # Add score labels and ticket counts
    for i, (score, count) in enumerate(zip(category_automation['mean'], category_automation['count'])):
        ax.text(score + 2, i, f'{score:.1f}  ({count:,} tickets)', va='center')
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='High (≥70)'),
        Patch(facecolor='#f39c12', label='Medium (50-69)'),
        Patch(facecolor='#e74c3c', label='Low (<50)')
    ]
    ax.legend(handles=legend_elements, loc='lower right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved automation by category: {output_path}")


def visualize_mttr_distribution(tickets_df, output_path='mttr_distribution.png'):
    """
    Visualize MTTR distribution
    Shows resolution time patterns
    """
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Remove outliers for better visualization
    mttr_clean = tickets_df['mttr_hours'].dropna()
    mttr_clean = mttr_clean[mttr_clean < 100]  # Remove extreme outliers
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Histogram
    ax1.hist(mttr_clean, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
    ax1.set_xlabel('MTTR (hours)', fontsize=12)
    ax1.set_ylabel('Number of Tickets', fontsize=12)
    ax1.set_title('MTTR Distribution', fontsize=14, fontweight='bold')
    ax1.axvline(mttr_clean.median(), color='red', linestyle='--', linewidth=2, label=f'Median: {mttr_clean.median():.1f}h')
    ax1.axvline(mttr_clean.mean(), color='orange', linestyle='--', linewidth=2, label=f'Mean: {mttr_clean.mean():.1f}h')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Box plot by category
    top_categories = tickets_df['l1_category'].value_counts().head(5).index
    data_by_cat = [tickets_df[tickets_df['l1_category'] == cat]['mttr_hours'].dropna() 
                   for cat in top_categories]
    
    ax2.boxplot(data_by_cat, labels=top_categories, patch_artist=True,
                boxprops=dict(facecolor='lightblue', alpha=0.7))
    ax2.set_ylabel('MTTR (hours)', fontsize=12)
    ax2.set_title('MTTR by Top 5 Categories', fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved MTTR distribution: {output_path}")


def visualize_time_trends(tickets_df, output_path='time_trends.png'):
    """
    Visualize ticket volume over time
    Shows trends, seasonality, peak times
    """
    import matplotlib.pyplot as plt
    import pandas as pd
    
    # Convert dates
    tickets_df['opened'] = pd.to_datetime(tickets_df['opened'], errors='coerce')
    tickets_df = tickets_df.dropna(subset=['opened'])
    
    # Group by month
    tickets_df['month'] = tickets_df['opened'].dt.to_period('M')
    monthly_counts = tickets_df.groupby('month').size()
    
    # Group by day of week
    tickets_df['day_of_week'] = tickets_df['opened'].dt.day_name()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    dow_counts = tickets_df['day_of_week'].value_counts().reindex(day_order, fill_value=0)
    
    # Group by hour
    tickets_df['hour'] = tickets_df['opened'].dt.hour
    hour_counts = tickets_df.groupby('hour').size()
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
    
    # Monthly trend
    ax1.plot(range(len(monthly_counts)), monthly_counts.values, marker='o', linewidth=2, color='steelblue')
    ax1.set_xticks(range(len(monthly_counts)))
    ax1.set_xticklabels([str(m) for m in monthly_counts.index], rotation=45)
    ax1.set_ylabel('Ticket Count', fontsize=12)
    ax1.set_title('Monthly Ticket Volume', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # Day of week
    colors_dow = ['#e74c3c' if day in ['Saturday', 'Sunday'] else 'steelblue' for day in day_order]
    ax2.bar(range(len(dow_counts)), dow_counts.values, color=colors_dow, alpha=0.8)
    ax2.set_xticks(range(len(dow_counts)))
    ax2.set_xticklabels(dow_counts.index, rotation=45)
    ax2.set_ylabel('Ticket Count', fontsize=12)
    ax2.set_title('Tickets by Day of Week', fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # Hour of day
    ax3.bar(hour_counts.index, hour_counts.values, color='steelblue', alpha=0.8)
    ax3.set_xlabel('Hour of Day (24h)', fontsize=12)
    ax3.set_ylabel('Ticket Count', fontsize=12)
    ax3.set_title('Tickets by Hour of Day', fontsize=14, fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    ax3.set_xticks(range(0, 24, 2))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Saved time trends: {output_path}")


def generate_all_visualizations(tickets_df, embeddings, cluster_labels, automation_scores, 
                                feature_importance, feature_names, upload_id):
    """
    Generate all 7 visualization graphs at once
    Call this after ML processing
    """
    output_dir = f'outputs/upload_{upload_id}'
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Generating All ML Visualizations for Upload {upload_id}")
    print(f"{'='*60}\n")
    
    # 1. BERT Clustering (2D)
    visualize_clusters(
        embeddings, cluster_labels, 
        tickets_df['short_description'].tolist()[:1000],
        output_path=f'{output_dir}/1_bert_clusters.png'
    )
    
    # 2. XGBoost Feature Importance (only from a trained model; drawn later by
    #    services.automation_scoring once SHAP values exist)
    if feature_importance is not None:
        visualize_xgboost_features(
            np.asarray(feature_importance), feature_names,
            output_path=f'{output_dir}/2_xgboost_features.png'
        )
    
    # 3. Automation Score Distribution
    visualize_automation_distribution(
        automation_scores,
        output_path=f'{output_dir}/3_automation_distribution.png'
    )
    
    # 4. Category Breakdown
    visualize_category_breakdown(
        tickets_df,
        output_path=f'{output_dir}/4_category_breakdown.png'
    )
    
    # 5. Automation by Category
    visualize_automation_by_category(
        tickets_df,
        output_path=f'{output_dir}/5_automation_by_category.png'
    )
    
    # 6. MTTR Distribution
    visualize_mttr_distribution(
        tickets_df,
        output_path=f'{output_dir}/6_mttr_distribution.png'
    )
    
    # 7. Time Trends
    visualize_time_trends(
        tickets_df,
        output_path=f'{output_dir}/7_time_trends.png'
    )
    
    print(f"\n{'='*60}")
    print(f"✅ All 7 Visualizations Saved to: {output_dir}")
    print(f"{'='*60}\n")
    
    return output_dir