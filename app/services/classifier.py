# app/services/classifier.py
import os
import re
import pickle
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import tempfile
import json

from app.core.logger import log
from app.core.config import settings
from app.core.database import execute_query, execute_update
from app.utils.text_utils import normalize_text

# Global classifier model
_classifier = None
_vectorizer = None
_model_loaded = False
_model_version = None


async def classify_document(text: str) -> Optional[Dict[str, Any]]:
    """
    Classify a document based on its text content.

    Args:
        text: Document text content

    Returns:
        Dictionary with classification results or None if classification failed
    """
    if not text:
        return None

    try:
        # Normalize text
        text = normalize_text(text)

        # Try rule-based classification first
        rule_result = await classify_by_rules(text)

        # If rule-based classification worked with high confidence, use it
        if rule_result and rule_result.get("confidence", 0) >= 0.8:
            return rule_result

        # Try ML-based classification if available
        ml_result = await classify_by_ml(text)

        # If ML classification worked with high confidence, use it
        if ml_result and ml_result.get("confidence", 0) >= 0.6:
            return ml_result

        # If both methods produced results, use the one with higher confidence
        if rule_result and ml_result:
            if rule_result.get("confidence", 0) >= ml_result.get("confidence", 0):
                return rule_result
            else:
                return ml_result

        # Return whichever result we have (or None if neither worked)
        return rule_result or ml_result

    except Exception as e:
        log.error(f"文書分類エラー: {e}")
        return None


async def classify_by_rules(text: str) -> Optional[Dict[str, Any]]:
    """
    Classify a document using rule-based approach.

    Args:
        text: Document text content

    Returns:
        Classification result or None if classification failed
    """
    try:
        # Load classifier config
        config = await load_classifier_config()
        if not config or not config.get("document_types"):
            return None

        best_match = None
        best_score = 0

        # Check each document type
        for doc_type in config.get("document_types", []):
            type_name = doc_type.get("name")
            keywords = doc_type.get("keywords", [])
            patterns = doc_type.get("patterns", [])

            if not type_name or not (keywords or patterns):
                continue

            # Calculate score based on keyword matches
            keyword_count = 0
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    keyword_count += 1

            keyword_score = keyword_count / max(1, len(keywords))

            # Calculate score based on pattern matches
            pattern_count = 0
            for pattern in patterns:
                regex = pattern.get("regex")
                if regex and re.search(regex, text):
                    pattern_count += 1

            pattern_score = pattern_count / max(1, len(patterns))

            # Combine scores (patterns are more important)
            combined_score = (keyword_score * 0.4) + (pattern_score * 0.6)

            # Track best match
            if combined_score > best_score:
                best_score = combined_score
                best_match = {
                    "doc_type": type_name,
                    "confidence": combined_score,
                    "method": "rule-based"
                }

        # Return best match if score is above threshold
        if best_match and best_match["confidence"] >= 0.3:
            return best_match

        return None

    except Exception as e:
        log.error(f"ルールベース分類エラー: {e}")
        return None


async def classify_by_ml(text: str) -> Optional[Dict[str, Any]]:
    """
    Classify a document using machine learning.

    Args:
        text: Document text content

    Returns:
        Classification result or None if classification failed
    """
    global _classifier, _vectorizer, _model_loaded

    try:
        # Check if model is loaded
        if not _model_loaded:
            await load_ml_model()

            # If still not loaded, fallback to rule-based
            if not _model_loaded:
                return None

        # Run classification in a separate thread to avoid blocking
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _classify_text_sync, text)

        return result

    except Exception as e:
        log.error(f"ML分類エラー: {e}")
        return None


def _classify_text_sync(text: str) -> Optional[Dict[str, Any]]:
    """
    Classify text using loaded ML model (synchronous version).

    Args:
        text: Document text

    Returns:
        Classification result or None if classification failed
    """
    global _classifier, _vectorizer

    if not _classifier or not _vectorizer:
        return None

    try:
        # Transform text to feature vector
        X = _vectorizer.transform([text])

        # Get prediction and probability
        doc_type = _classifier.predict(X)[0]
        probabilities = _classifier.predict_proba(X)[0]

        # Get index of predicted class
        class_idx = list(_classifier.classes_).index(doc_type)
        confidence = probabilities[class_idx]

        return {
            "doc_type": doc_type,
            "confidence": float(confidence),
            "method": "ml"
        }

    except Exception as e:
        log.error(f"同期ML分類エラー: {e}")
        return None


async def load_ml_model():
    """
    Load the ML classification model.
    """
    global _classifier, _vectorizer, _model_loaded, _model_version

    try:
        # Check if model files exist
        model_dir = os.path.join("models")
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, "classifier.pkl")
        vectorizer_path = os.path.join(model_dir, "vectorizer.pkl")
        version_path = os.path.join(model_dir, "version.json")

        if not os.path.exists(model_path) or not os.path.exists(vectorizer_path):
            log.warning("分類器モデルファイルが見つかりません。学習が必要です。")
            _model_loaded = False
            return

        # Load version info
        if os.path.exists(version_path):
            with open(version_path, "r", encoding="utf-8") as f:
                version_info = json.load(f)
                _model_version = version_info.get("version")

        # Load model and vectorizer
        loop = asyncio.get_running_loop()

        _classifier = await loop.run_in_executor(
            None,
            lambda: pickle.load(open(model_path, "rb"))
        )

        _vectorizer = await loop.run_in_executor(
            None,
            lambda: pickle.load(open(vectorizer_path, "rb"))
        )

        _model_loaded = True
        log.info(f"分類器モデルのロード完了 (version: {_model_version})")

    except Exception as e:
        log.error(f"分類器モデルのロードエラー: {e}")
        _model_loaded = False


async def load_classifier_config() -> Dict[str, Any]:
    """
    Load classifier configuration from file.

    Returns:
        Classifier configuration
    """
    try:
        config_path = os.path.join("config", "classifier_config.yaml")
        if not os.path.exists(config_path):
            log.warning(f"分類器設定ファイルが見つかりません: {config_path}")
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config

    except Exception as e:
        log.error(f"分類器設定のロードエラー: {e}")
        return {}


async def retrain_classifier():
    """
    Retrain the classifier with feedback data.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.ensemble import RandomForestClassifier

        # Get feedback data
        feedback_data = await execute_query(
            """
            SELECT d.id, d.doc_type, dc.content, f.original_classification, f.corrected_classification
            FROM feedback f
            JOIN documents d ON f.document_id = d.id
            JOIN document_content dc ON d.id = dc.document_id
            WHERE f.applied = 0
            """
        )

        if not feedback_data or len(feedback_data) < 5:
            log.warning(f"再学習のためのフィードバックデータが不足しています: {len(feedback_data) if feedback_data else 0}件")
            return

        # Get existing training data
        training_data = await execute_query(
            """
            SELECT d.id, d.doc_type, dc.content
            FROM documents d
            JOIN document_content dc ON d.id = dc.document_id
            WHERE d.doc_type IS NOT NULL
            AND d.id NOT IN (SELECT document_id FROM feedback WHERE applied = 0)
            LIMIT 1000
            """
        )

        # Prepare training data
        texts = []
        labels = []

        # Add existing data
        for item in training_data:
            text = item["content"]
            doc_type = item["doc_type"]

            if text and doc_type:
                texts.append(normalize_text(text))
                labels.append(doc_type)

        # Add feedback data (use corrected classification)
        for item in feedback_data:
            text = item["content"]
            doc_type = item["corrected_classification"]

            if text and doc_type:
                texts.append(normalize_text(text))
                labels.append(doc_type)

        if len(texts) < 10:
            log.warning(f"学習データが不足しています: {len(texts)}件")
            return

        # Train vectorizer
        vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        X = vectorizer.fit_transform(texts)

        # Train classifier
        classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42
        )
        classifier.fit(X, labels)

        # Save model
        model_dir = os.path.join("models")
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, "classifier.pkl")
        vectorizer_path = os.path.join(model_dir, "vectorizer.pkl")
        version_path = os.path.join(model_dir, "version.json")

        # Save versions with timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_model_path = os.path.join(model_dir, f"classifier_{timestamp}.pkl")
        temp_vectorizer_path = os.path.join(model_dir, f"vectorizer_{timestamp}.pkl")

        # Save to temporary files first
        with open(temp_model_path, "wb") as f:
            pickle.dump(classifier, f)

        with open(temp_vectorizer_path, "wb") as f:
            pickle.dump(vectorizer, f)

        # Save version info
        version_info = {
            "version": timestamp,
            "training_samples": len(texts),
            "document_types": list(set(labels)),
            "feedback_samples": len(feedback_data),
            "trained_at": datetime.now().isoformat()
        }

        with open(version_path, "w", encoding="utf-8") as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)

        # Rename to final paths
        os.replace(temp_model_path, model_path)
        os.replace(temp_vectorizer_path, vectorizer_path)

        # Mark feedback as applied
        await execute_update(
            """
            UPDATE feedback
            SET applied = 1
            WHERE applied = 0
            """
        )

        # Update global model
        global _classifier, _vectorizer, _model_loaded, _model_version
        _classifier = classifier
        _vectorizer = vectorizer
        _model_loaded = True
        _model_version = timestamp

        log.info(f"分類器の再学習完了: {len(texts)}件のサンプルで学習 (version: {timestamp})")

    except Exception as e:
        log.error(f"分類器再学習エラー: {e}")