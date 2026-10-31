"""
automation_ml.py
----------------
ML-based automation classification using XGBoost + BERT embeddings.
Learns from rule-based labels and human corrections.
"""

import os
import pickle
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ML imports (with fallbacks)
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("Warning: sklearn not available, ML features disabled")

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

# Model storage path
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'automation_classifier.pkl')
VECTORIZER_PATH = os.path.join(MODEL_DIR, 'tfidf_vectorizer.pkl')
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, 'label_encoder.pkl')


class AutomationMLClassifier:
    """
    ML classifier for automation status prediction.
    Uses TF-IDF + XGBoost (or RandomForest fallback).
    """
    
    def __init__(self):
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.is_trained = False
        self.feature_names = []
        
        # Ensure model directory exists
        os.makedirs(MODEL_DIR, exist_ok=True)
        
        # Try to load existing model
        self._load_model()
    
    def _load_model(self) -> bool:
        """Load trained model from disk"""
        try:
            if os.path.exists(MODEL_PATH):
                with open(MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                with open(VECTORIZER_PATH, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                with open(LABEL_ENCODER_PATH, 'rb') as f:
                    self.label_encoder = pickle.load(f)
                self.is_trained = True
                print(f"ML model loaded from {MODEL_PATH}")
                return True
        except Exception as e:
            print(f"Could not load ML model: {e}")
        return False
    
    def _save_model(self):
        """Save trained model to disk"""
        try:
            with open(MODEL_PATH, 'wb') as f:
                pickle.dump(self.model, f)
            with open(VECTORIZER_PATH, 'wb') as f:
                pickle.dump(self.vectorizer, f)
            with open(LABEL_ENCODER_PATH, 'wb') as f:
                pickle.dump(self.label_encoder, f)
            print(f"ML model saved to {MODEL_PATH}")
        except Exception as e:
            print(f"Could not save ML model: {e}")
    
    def _extract_features(self, ticket: Dict) -> str:
        """
        Extract text features from ticket for ML.
        Combines multiple fields into single text.
        """
        parts = []
        
        # Text fields
        short_desc = str(ticket.get('short_description', ''))
        resolution_notes = str(ticket.get('resolution_notes', '') or ticket.get('close_notes', ''))
        category = str(ticket.get('category', ''))
        subcategory = str(ticket.get('subcategory', ''))
        channel = str(ticket.get('channel', ''))
        assignment_group = str(ticket.get('assignment_group', ''))
        resolved_by = str(ticket.get('resolved_by', ''))
        
        # Combine text
        parts.append(f"DESC: {short_desc}")
        parts.append(f"RES: {resolution_notes[:200]}")  # Limit resolution notes
        parts.append(f"CAT: {category} {subcategory}")
        parts.append(f"CHANNEL: {channel}")
        parts.append(f"GROUP: {assignment_group}")
        parts.append(f"RESOLVER: {resolved_by}")
        
        # Add numeric features as text tokens
        mttr_hours = ticket.get('mttr_hours')
        if mttr_hours is not None:
            if mttr_hours < 0.25:
                parts.append("MTTR_VERY_FAST")
            elif mttr_hours < 0.5:
                parts.append("MTTR_FAST")
            elif mttr_hours < 1:
                parts.append("MTTR_MEDIUM")
            elif mttr_hours < 4:
                parts.append("MTTR_SLOW")
            else:
                parts.append("MTTR_VERY_SLOW")
        
        reassignment = int(ticket.get('reassignment_count', 0) or 0)
        if reassignment == 0:
            parts.append("REASSIGN_NONE")
        elif reassignment == 1:
            parts.append("REASSIGN_ONE")
        else:
            parts.append("REASSIGN_MULTIPLE")
        
        return ' '.join(parts)
    
    def _prepare_training_data(self, tickets: List[Dict]) -> Tuple[List[str], List[str]]:
        """
        Prepare training data from tickets.
        
        Args:
            tickets: List of ticket dicts with 'aiops_automation_status' label
            
        Returns:
            (X_texts, y_labels)
        """
        X_texts = []
        y_labels = []
        
        for ticket in tickets:
            status = ticket.get('aiops_automation_status')
            if status and status != 'Excluded':
                text = self._extract_features(ticket)
                X_texts.append(text)
                y_labels.append(status)
        
        return X_texts, y_labels
    
    def train(self, tickets: List[Dict], min_samples: int = 100) -> Dict:
        """
        Train ML model on labeled tickets.
        
        Args:
            tickets: List of ticket dicts with labels
            min_samples: Minimum samples required for training
            
        Returns:
            Training metrics
        """
        if not HAS_SKLEARN:
            return {'error': 'sklearn not available'}
        
        X_texts, y_labels = self._prepare_training_data(tickets)
        
        if len(X_texts) < min_samples:
            return {
                'error': f'Not enough samples: {len(X_texts)} < {min_samples}',
                'samples': len(X_texts)
            }
        
        print(f"Training ML model with {len(X_texts)} samples...")
        
        # Encode labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y_labels)
        
        # Vectorize text
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words='english',
            min_df=2,
            max_df=0.95
        )
        X_vectors = self.vectorizer.fit_transform(X_texts)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_vectors, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Train model
        if HAS_XGBOOST:
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss'
            )
        else:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Get class distribution
        class_dist = {}
        for label in y_labels:
            class_dist[label] = class_dist.get(label, 0) + 1
        
        self.is_trained = True
        self._save_model()
        
        print(f"ML model trained. Accuracy: {accuracy:.2%}")
        
        return {
            'success': True,
            'samples': len(X_texts),
            'accuracy': accuracy,
            'class_distribution': class_dist,
            'model_type': 'XGBoost' if HAS_XGBOOST else 'RandomForest',
        }
    
    def predict(self, ticket: Dict) -> Optional[Dict]:
        """
        Predict automation status for a ticket.
        
        Args:
            ticket: Ticket dict
            
        Returns:
            {
                'status': predicted status,
                'confidence': 0-100,
                'probabilities': {class: prob}
            }
            or None if model not trained
        """
        if not self.is_trained or not HAS_SKLEARN:
            return None
        
        try:
            text = self._extract_features(ticket)
            X = self.vectorizer.transform([text])
            
            # Get prediction and probabilities
            pred_encoded = self.model.predict(X)[0]
            pred_proba = self.model.predict_proba(X)[0]
            
            status = self.label_encoder.inverse_transform([pred_encoded])[0]
            confidence = int(max(pred_proba) * 100)
            
            # Get all class probabilities
            probabilities = {}
            for i, cls in enumerate(self.label_encoder.classes_):
                probabilities[cls] = float(pred_proba[i])
            
            return {
                'status': status,
                'confidence': confidence,
                'probabilities': probabilities,
            }
            
        except Exception as e:
            print(f"ML prediction error: {e}")
            return None
    
    def predict_batch(self, tickets: List[Dict]) -> List[Optional[Dict]]:
        """Predict for multiple tickets"""
        return [self.predict(t) for t in tickets]


# Global classifier instance
_ml_classifier = None


def get_ml_classifier() -> AutomationMLClassifier:
    """Get or create ML classifier instance"""
    global _ml_classifier
    if _ml_classifier is None:
        _ml_classifier = AutomationMLClassifier()
    return _ml_classifier


def train_ml_model(tickets: List[Dict]) -> Dict:
    """Train ML model on labeled tickets"""
    classifier = get_ml_classifier()
    return classifier.train(tickets)


def predict_with_ml(ticket: Dict) -> Optional[Dict]:
    """Predict using ML model"""
    classifier = get_ml_classifier()
    return classifier.predict(ticket)


def is_ml_available() -> bool:
    """Check if ML model is trained and available"""
    classifier = get_ml_classifier()
    return classifier.is_trained