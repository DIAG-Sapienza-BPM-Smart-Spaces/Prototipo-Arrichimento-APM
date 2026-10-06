#!/bin/bash
# temizle.sh — ProjectSapienza_NEW klasorunu profesore verilecek sekilde temizler.
# Calisan sistemin kullandigi hicbir dosyaya dokunmaz. rm -f: olmayan dosyalari atlar.
# Kullanim:  proje klasorunde ->  bash temizle.sh
set -u
echo "== ProjectSapienza_NEW temizlik =="

# 1) Tek seferlik yamalar (uygulandi, artik gereksiz)
rm -f ./*_patch.py

# 2) Tum yedekler (.bak ve .bak_*)
rm -f ./*.bak ./*.bak_*

# 3) Emekli kesif dongusu (yeni sistem taxonomy_cleanup kullaniyor)
rm -f discover.py promote.py orphan_pool.py nightly_discovery.py run_nightly.sh \
      provisional_terms.json discovery_log.jsonl

# 4) Eski batch/deneme scriptleri
rm -f tf_induce_field.py tf_phase1_harvest.py tf_minimal_seed_test.py \
      tf_compare_modes.py tf_azione_split.py tf_azione_apply.py

# 5) Python onbellegi
rm -rf __pycache__

# 6) taxonomy_free/ icindeki eski batch ciktilari (online *_online.json KALIR)
rm -f taxonomy_free/induced_taxonomy*.json taxonomy_free/c_desc*.json \
      taxonomy_free/c_descriptions*.json taxonomy_free/*_report*.md \
      taxonomy_free/c_granularity*.md taxonomy_free/*.bak

# 7) Olcum/degerlendirme araclari -> silmek yerine eval/ klasorune tasi (tez icin durur)
mkdir -p eval
mv -f tf_name_eval.py tf_cluster_compare.py tf_componente_eval.py evaluator.py \
      name_gold_dolu*.xlsx clustering_comparison_EN.md eval/ 2>/dev/null

echo
echo "Bitti. Klasorde kalmasi gerekenler:"
echo "  Kod:  main.py router.py keyword_extractor.py validator.py text_cleaner.py"
echo "        config.py online_taxonomy.py name_normalizer.py tf_c_bootstrap.py"
echo "        azione_extractor.py taxonomy_cleanup.py"
echo "  Veri: reference_vocabulary.json reference_vocabulary_sintomo.json"
echo "        keyword_taxonomy.json material_map.json learned_mappings.json requirements.txt"
echo "  Klasor: input/ output/ taxonomy_free/ eval/"
echo
echo "Not: _yedek/ klasorunu güvenlik icin BIRAKTIM. Emin olunca:  rm -rf _yedek"
echo "Kalanlari gormek icin:  ls -la"
