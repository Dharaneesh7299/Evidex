"""Sample data generation and seeding for Evidex.

Creates realistic, verifiable scientific research PDFs in the uploads directory
and seeds a complete sample investigation. Every claim, finding, and citation
in the sample investigation directly references exact extracted page text from
the generated PDFs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

from app.core.config import get_settings
from app.db.database import Database
from app.services.pdf_service import chunk_pages, extract_metadata, extract_pages

logger = logging.getLogger(__name__)

SAMPLE_INVESTIGATION_ID = "inv_sample_medai_001"
SAMPLE_QUESTION = "Does this technique consistently improve classification accuracy across different datasets, and what limitations affect the findings?"

SAMPLE_PAPERS_CONFIG = [
    {
        "id": "paper_chen2023_sample",
        "filename": "chen2023_multiscale_transformers.pdf",
        "title": "Multi-Scale Vision Transformers for Dermoscopic Lesion Classification",
        "authors": "H. Chen, Y. Zhang, M. Davis",
        "year": "2023",
        "pages": [
            # Page 1
            """Multi-Scale Vision Transformers for Dermoscopic Lesion Classification
H. Chen, Y. Zhang, M. Davis
Department of Biomedical Informatics, Stanford University (2023)

Abstract
Automated skin cancer screening requires discriminating subtle morphologic characteristics in cutaneous lesions. We propose a hierarchical multi-scale vision transformer architecture (MS-ViT) designed to capture fine-grained dermoscopic pigment network boundaries alongside global lesion symmetry. Evaluated on the ISIC-2020 archive comprising 33,126 dermoscopic images, MS-ViT achieved a top-1 balanced accuracy of 89.4% and an area under the ROC curve (AUC) of 0.942, outperforming the standard ResNet-50 baseline by 4.2%.

1. Introduction
Early diagnosis of malignant melanoma significantly improves 5-year patient survival rates. Recent advancements in deep convolutional neural networks (CNNs) have shown dermatologist-level classification capabilities in controlled experimental settings. However, conventional CNNs rely on localized receptive fields that often miss long-range architectural relationships across irregular lesion margins. Vision transformers provide self-attention mechanisms capable of modeling arbitrary spatial dependencies.""",
            # Page 2
            """2. Methodology and Experimental Setup
The proposed MS-ViT pipeline partitions input images into multi-resolution patch tokens (16x16 and 8x8) to simultaneously encode microscopic cellular texture and macroscopic border irregularity.

Training Configuration:
- Optimizer: AdamW with weight decay 0.05
- Learning rate: 1e-4 with cosine learning rate decay
- Training duration: 100 epochs with batch size 64
- Resolution: All images standardized to 384x384 pixels
- Baselines: ResNet-50 and EfficientNet-B4 pretrained on ImageNet-1k

Dataset and Preprocessing:
We utilized the International Skin Imaging Collaboration (ISIC) 2020 dataset containing 33,126 dermoscopic images spanning 7 diagnostic classes: melanoma, melanocytic nevus, basal cell carcinoma, actinic keratosis, benign keratosis, dermatofibroma, and vascular lesion. Data augmentation included color jittering, random rotation (+/- 45 degrees), and subtle Gaussian blur to simulate real-world photographic variation.""",
            # Page 3
            """3. Results and Empirical Findings
Evaluation was performed on an independent test partition of 4,500 held-out images. 

Reported Results:
On the held-out ISIC validation set, our multi-scale transformer consistently improved classification accuracy across different lesion subtypes, achieving 91.2% sensitivity for melanoma detection and 89.4% overall balanced accuracy. The model demonstrated superior feature discriminability compared to ResNet-50 (85.2%) and EfficientNet-B4 (86.7%).

Subgroup Performance Disparity:
When disaggregating results across patient demographic groups, classification accuracy degraded by 6.8% when evaluated on dark skin phenotypes (Fitzpatrick skin types IV-VI). In these underrepresented cohorts, training representation accounted for less than 4% of total dataset samples, resulting in elevated false positive rates for benign pigmented lesions.""",
            # Page 4
            """4. Limitations and Discussion
While the empirical results substantiate high discriminative capacity on standardized benchmarks, several critical limitations must be highlighted:

1. Acquisition Modality Dependency: The model was trained exclusively on epiluminescence contact dermoscopy. When evaluated on clinical macroscopic photography captured via consumer mobile smartphones, accuracy dropped sharply by 14.3% due to uncontrolled illumination, specular glare, and lack of specialized polarized lighting.

2. Computational Overhead: The multi-scale self-attention mechanism requires 22.4 GFLOPs per forward pass, resulting in 4.3x higher latency compared to MobileNetV3. This latency presents deployment challenges for low-power handheld clinical devices in rural clinics.

3. Lack of Prospective Validation: The retrospective design does not account for clinician interaction dynamics, biopsy thresholds, or multi-lesion clinical prioritization."""
        ],
    },
    {
        "id": "paper_kumar2024_sample",
        "filename": "kumar2024_diffusion_augmentation.pdf",
        "title": "Diffusion-Augmented Contrastive Learning in Low-Data Histopathology Regimes",
        "authors": "R. Kumar, S. Patel, E. Vance",
        "year": "2024",
        "pages": [
            # Page 1
            """Diffusion-Augmented Contrastive Learning in Low-Data Histopathology Regimes
R. Kumar, S. Patel, E. Vance
Computational Pathology Laboratory, Johns Hopkins University (2024)

Abstract
Deep learning models in computational pathology encounter severe performance deterioration when target biopsy classes have limited annotated samples. We introduce Diff-AugCLR, a framework combining conditional latent diffusion models with self-supervised contrastive learning to synthesize diverse cellular morphology and reinforce representation learning. Evaluated across two diverse histopathology benchmarks (Camelyon16 and TCGA-COAD), our framework demonstrates substantial robustness improvements in low-label regimes.

1. Introduction
Histopathologic classification of whole-slide images (WSIs) forms the gold standard for oncologic staging. However, annotating gigapixel slides requires substantial pathologist time, leading to severe label scarcity for uncommon neoplastic subtypes. While standard geometric transformations provide basic data augmentation, they cannot synthesize diverse nuclear pleomorphism, chromatin distribution, or glandular architectural variation.""",
            # Page 2
            """2. Methods and Multi-Dataset Benchmarks
We implemented a two-stage pipeline: a class-conditional latent diffusion model trained on tissue patches, followed by MoCo-v3 contrastive pre-training using both real and synthesized histological patches.

Datasets:
1. Camelyon16: 400 whole-slide images for breast cancer sentinel lymph node metastasis detection. Tissue patches extracted at 20x magnification (0.5 um/pixel).
2. TCGA-COAD: The Cancer Genome Atlas colorectal adenocarcinoma cohort containing 460 patients. Patches extracted across 9 morphological tissue categories including tumor, stroma, and normal mucosa.

Experimental Evaluation Regimes:
To test label efficiency, models were fine-tuned using stratified subsets of 5%, 10%, and 25% labeled training slides, evaluated against fully supervised baselines.""",
            # Page 3
            """3. Comparative Findings Across Datasets
Across both Camelyon16 and TCGA datasets, the technique consistently improved classification accuracy by an average margin of 5.8% in low-data regimes. 

Specific Metric Gains:
On Camelyon16 with only 10% labeled data, the baseline ResNet-50 attained an AUC of 0.812, whereas Diff-AugCLR achieved an AUC of 0.887 (+7.5% absolute gain). On the multi-class TCGA-COAD benchmark with 10% labels, balanced accuracy increased from 74.3% to 80.9%.

Plateau in High-Data Regimes:
Importantly, when labeled training data exceeded 50% of available slides, diffusion augmentation yielded no statistically significant improvement over standard affine transformations (AUC 0.941 vs 0.939, p = 0.42). In high-data regimes, real sample diversity already saturates model capacity.""",
            # Page 4
            """4. Limitations and Architectural Boundaries
Our experimental findings reveal several key limitations:

1. Hallucination Risk: In approximately 2.3% of generated high-grade tumor tiles, the diffusion model synthesized non-biological nuclear configurations that do not correspond to valid histological criteria.

2. Hardware and Training Cost: Training the high-resolution conditional diffusion model required 4x NVIDIA A100 GPUs for 72 hours, consuming significant electrical power.

3. Patch-Level Confinement: The current framework operates on localized 512x512 patches and does not model organ-level macroscopic tissue architecture or vascular invasion patterns spanning multiple millimeters."""
        ],
    },
    {
        "id": "paper_torres2024_sample",
        "filename": "torres2024_multicenter_generalization.pdf",
        "title": "Robustness and Generalization Limits of Deep Ensembles across Multi-Center Clinical Imaging",
        "authors": "A. Torres, J. M. Lindqvist, K. Zhao",
        "year": "2024",
        "pages": [
            # Page 1
            """Robustness and Generalization Limits of Deep Ensembles across Multi-Center Clinical Imaging
A. Torres, J. M. Lindqvist, K. Zhao
Center for Medical AI, Karolinska Institute (2024)

Abstract
While recent machine learning literature reports stellar classification accuracy on curated research datasets, cross-center clinical transportability remains an open problem. We conduct a rigorous multi-institution study evaluating whether deep architectures and ensemble methods consistently maintain classification accuracy across diverse hospital acquisition pipelines without site-specific recalibration.

1. Introduction
The translation of medical imaging algorithms from bench to bedside is frequently stymied by out-of-distribution performance drops. Variations in scanner hardware manufacturers, radiologic technician positioning, contrast agent timing, and patient demographics introduce systemic domain shifts. A technique that demonstrates state-of-the-art accuracy in an originating academic medical center may degrade substantially when deployed in a community hospital.""",
            # Page 2
            """2. Multi-Center Study Protocol
We compiled 14,800 medical imaging studies across four geographically separate hospital networks:
- Hospital A (Originating center): Academic hospital utilizing GE Healthcare 64-slice CT and digital radiography.
- Hospital B: Regional medical center using Siemens Somatom scanners.
- Hospital C: Urban trauma center with Philips Brilliance systems and high trauma prevalence.
- Hospital D: Rural ambulatory clinic with portable digital X-ray equipment.

Evaluation Metrics:
Performance was measured using Area Under the ROC Curve (AUC), Expected Calibration Error (ECE), and worst-case subgroup sensitivity across diagnostic indications.""",
            # Page 3
            """3. Cross-Site Performance Disagreements
Our empirical findings reveal significant domain sensitivity:
While the proposed ensemble architecture achieved an in-distribution AUC of 0.931 on Hospital A data, performance dropped to 0.824 on Hospital C and 0.795 on Hospital D. 

The technique does not consistently improve classification accuracy across heterogeneous clinical centers unless explicit domain adaptation or scanner normalization is applied.

Contrary to claims that novel transformer architectures intrinsically resolve domain shifts, our evidence demonstrates that deep model predictions remain vulnerable to scanner manufacturer variations, slice thickness discrepancies, and institutional patient mix differences.""",
            # Page 4
            """4. Methodological Conclusions and Recommendations
Our analysis underscores the following boundaries:

1. Calibration Drift: Even when discrimination remained acceptable, model confidence scores drifted significantly; Expected Calibration Error increased from 0.042 (Hospital A) to 0.168 (Hospital C), producing overconfident incorrect classifications.

2. Necessity of Standardized Acquisition: Algorithmic improvements alone cannot overcome raw acquisition discrepancies; institutional DICOM standardization protocols are essential prerequisites for reliable clinical AI.

3. Verification Requirement: Independent multi-center validation must be required by regulatory agencies prior to clinical clearance."""
        ],
    },
]


def create_pdf_from_text(pages: List[str], output_path: Path, metadata: Optional[dict] = None) -> int:
    """Create a formatted multi-page PDF using PyMuPDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    if metadata:
        doc.set_metadata(metadata)

    for page_text in pages:
        page = doc.new_page(width=595, height=842)  # A4 size
        # Format text with margin
        rect = fitz.Rect(50, 50, 545, 792)
        page.insert_textbox(rect, page_text, fontsize=10, fontname="helv", color=(0.12, 0.13, 0.15))

    doc.save(str(output_path))
    doc.close()
    return len(pages)


def seed_sample_data(db: Database) -> str:
    """Generate sample PDF files, ingest into DB, and run the complete sample investigation."""
    settings = get_settings()
    sample_dir = settings.upload_dir / "sample_papers"
    sample_dir.mkdir(parents=True, exist_ok=True)

    seeded_paper_ids: List[str] = []

    for cfg in SAMPLE_PAPERS_CONFIG:
        paper_id = cfg["id"]
        pdf_filename = cfg["filename"]
        pdf_path = sample_dir / pdf_filename

        # Always ensure PDF file exists on disk with structured metadata
        pdf_meta = {
            "title": cfg["title"],
            "author": cfg["authors"],
            "subject": cfg["year"],
        }
        page_count = create_pdf_from_text(cfg["pages"], pdf_path, metadata=pdf_meta)
        file_size = pdf_path.stat().st_size

        # Ingest into DB if not already present
        existing = db.get_paper(paper_id)
        if not existing:
            extracted_pages = extract_pages(pdf_path)
            char_count = sum(len(p.text) for p in extracted_pages)
            chunks = chunk_pages(paper_id, extracted_pages)

            db.create_paper({
                "id": paper_id,
                "title": cfg["title"],
                "authors": cfg["authors"],
                "year": cfg["year"],
                "original_filename": pdf_filename,
                "stored_path": str(pdf_path),
                "file_size": file_size,
                "page_count": page_count,
                "char_count": char_count,
                "status": "ready",
                "metadata": {
                    "title": cfg["title"],
                    "authors": cfg["authors"],
                    "year": cfg["year"],
                    "confidence": "high",
                    "notes": "Verified sample research document with grounded citations.",
                },
            })
            db.insert_chunks(paper_id, [c.__dict__ for c in chunks])
            logger.info(f"Seeded sample paper '{paper_id}' ({page_count} pages, {len(chunks)} chunks).")

        seeded_paper_ids.append(paper_id)

    # Check if sample investigation exists
    existing_inv = db.get_investigation(SAMPLE_INVESTIGATION_ID)
    if existing_inv and existing_inv.get("status") == "completed":
        logger.info(f"Sample investigation '{SAMPLE_INVESTIGATION_ID}' already exists and is completed.")
        return SAMPLE_INVESTIGATION_ID

    # Create and run sample investigation
    logger.info(f"Creating sample investigation '{SAMPLE_INVESTIGATION_ID}'...")
    from app.agents.orchestrator import ResearchOrchestrator

    # Ensure clean record
    with db.transaction() as conn:
        conn.execute("DELETE FROM investigations WHERE id = ?", [SAMPLE_INVESTIGATION_ID])
        conn.execute(
            """
            INSERT INTO investigations
                (id, research_question, status, stage, progress, paper_ids_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            [
                SAMPLE_INVESTIGATION_ID,
                SAMPLE_QUESTION,
                "pending",
                "queued",
                0,
                db._dumps(seeded_paper_ids),
            ],
        )

    orchestrator = ResearchOrchestrator(db)
    orchestrator.run_investigation(SAMPLE_INVESTIGATION_ID)
    logger.info(f"Sample investigation '{SAMPLE_INVESTIGATION_ID}' executed successfully.")
    return SAMPLE_INVESTIGATION_ID
