# DEPRECATED: Use xml_parser.py instead. This file retained for backward compatibility.
# The StenograficoIngester class still provides XML parsing methods (parse_xml_file,
# parse_intervento, parse_votazione, etc.) but all Neo4j write methods and the
# standalone main() have been removed. New code should use StenograficoParser from
# xml_parser.py and DatabaseBuilder from db_builder.py.
"""
ingest_stenografici.py — DEPRECATED XML parsing helpers.

Retained for backward compatibility only. Do not use for new code.
Parser methods: parse_xml_file, parse_intervento, parse_votazione,
                extract_text_from_element, get_nominativo_info,
                merge_continuation_interventions, preprocess_text_with_alignment,
                create_chunks, clean_text.
Removed: save_to_neo4j, clear_stenografici_data, create_constraints,
         create_indexes, __init__ (Neo4j driver), close, main().
"""

import os
import re
import glob
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple
import hashlib
import regex as regex_lib

# Chunking constants (kept for backward compat — new code uses BuildConfig)
CHUNK_SIZE = 1200  # caratteri target per chunk (ottimizzato per contesto semantico)
CHUNK_OVERLAP = 250  # overlap tra chunk consecutivi
MIN_INTERVENTO_LENGTH = 100  # minimo caratteri per salvare un intervento


class StenograficoIngester:
    def __init__(self):
        # Neo4j driver removed — this class is a pure parser only.
        # Use StenograficoParser from xml_parser.py for new code.
        self.ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
        self.audit_buffer = []
        self.stats = {
            'processed_interventi': 0,
            'with_removals': 0,
            'total_parentheticals_removed': 0,
            'total_markers_removed': 0,
            'total_fallback_alignment': 0
        }

    def merge_continuation_interventions(self, interventi: List[Dict]) -> List[Dict]:
        """
        Unisce interventi consecutivi dello stesso oratore se il secondo inizia con ellissi (...).
        Gestisce chain di 3+ interventi.
        """
        if not interventi:
            return []
            
        merged_list = []
        skip_indices = set()
        
        n = len(interventi)
        i = 0
        while i < n:
            if i in skip_indices:
                i += 1
                continue
                
            current = interventi[i]
            
            # Cerca catena di continuazioni
            j = i + 1
            while j < n:
                next_int = interventi[j]
                
                # Criterio 1: Stesso deputato (e non PRESIDENTE, ma parse_intervento scarta già PRESDIENTE)
                # Confronta deputato_id (priorità) o cognome_nome
                same_speaker = False
                if current.get('deputato_id') and next_int.get('deputato_id'):
                    same_speaker = current['deputato_id'] == next_int['deputato_id']
                elif current.get('cognome_nome') and next_int.get('cognome_nome'):
                    # Fallback string comparison
                    nw1 = re.sub(r'\s+', ' ', current['cognome_nome']).strip().lower()
                    nw2 = re.sub(r'\s+', ' ', next_int['cognome_nome']).strip().lower()
                    same_speaker = (nw1 == nw2)
                
                if not same_speaker:
                    break
                
                # Criterio 2: Il secondo inizia con ellissi nel RAW
                raw_next = next_int.get('testo_raw', '')
                # Rimuovi eventuali intestazioni se rimaste (ma parse_intervento le toglie)
                # Verifica pattern ellissi
                # Supporta: "...", "…", ". . ." con spazi opzionali iniziali
                # Nota: testo_raw è già "main_text" pulito dal parser (senza nome oratore)
                ellipsis_match = re.match(r'^\s*(?:\.{3}|…|\.\s\.\s\.)', raw_next)
                
                if not ellipsis_match:
                    break
                    
                # TROVATO MERGE!
                # 1. Unisci testi
                # Unisci RAW
                sep = " " if not current['testo_raw'].endswith(" ") else ""
                current['testo_raw'] += sep + raw_next
                
                # Unisci Preprocessed (necessario ricalcolare o unire?)
                # Meglio unire e basta, assumendo che preprocessing sia "lineare" oppure rilanciare preprocessing?
                # Rilanciamo preprocessing sul nuovo raw per sicurezza (allineamento!)
                
                # 2. Aggiorna metadati
                if 'merged_from_ids' not in current:
                    current['merged_from_ids'] = []
                current['merged_from_ids'].append(next_int['original_id'])
                
                # 3. Aggiorna char count
                # Sarà aggiornato dopo ri-preprocessing
                
                # Logging
                # print(f"Merging intervention {next_int['original_id']} into {current['original_id']} (Speaker: {current.get('cognome_nome')})")
                
                skip_indices.add(j)
                j += 1
            
            # Se abbiamo fatto merge, ricalcola preprocessing e chunks
            if 'merged_from_ids' in current:
                # Riesegui preprocessing su tutto il raw unito
                clean_text, al_map, stats = self.preprocess_text_with_alignment(current['testo_raw'])
                current['testo_preprocessed'] = clean_text
                current['testo'] = clean_text
                current['alignment_map'] = al_map # New map for the full text
                current['char_count'] = len(clean_text)
                
                # Aggiorna stats globali con quelle del nuovo passo (sovrascrivendo o sommando?)
                # È un po' tricky correggere le stats precedenti. 
                # Semplifichiamo: non rettifichiamo le stats degli interventi singoli "persi".
                
            merged_list.append(current)
            i = j # Salta quelli uniti
            
        return merged_list

    def extract_text_from_element(self, element) -> str:
        """Estrae tutto il testo da un elemento XML, inclusi i sottoelementi."""
        if element is None:
            return ""

        text_parts = []
        if element.text:
            text_parts.append(element.text.strip())

        for child in element:
            # Estrai il testo del tag nominativo
            if child.tag == 'nominativo':
                if child.text:
                    text_parts.append(child.text.strip())
            elif child.tag == 'emphasis':
                if child.text:
                    text_parts.append(child.text.strip())
            else:
                text_parts.append(self.extract_text_from_element(child))

            if child.tail:
                text_parts.append(child.tail.strip())

        return ' '.join(filter(None, text_parts))

    def get_nominativo_info(self, testo_xhtml) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Estrae id deputato, cognomeNome e se è PRESIDENTE dal testoXHTML.
        Returns: (deputato_id, cognome_nome, is_presidente)
        """
        nominativo = testo_xhtml.find('nominativo') if testo_xhtml is not None else None
        if nominativo is not None:
            dep_id = nominativo.get('id')
            cognome_nome = nominativo.get('cognomeNome')
            is_presidente = nominativo.text and nominativo.text.strip() == "PRESIDENTE"
            return dep_id, cognome_nome, is_presidente
        return None, None, False

    def clean_text(self, text: str) -> str:
        """Pulisce il testo rimuovendo spazi multipli e caratteri speciali."""
        if not text:
            return ""
        # Rimuovi spazi multipli
        text = re.sub(r'\s+', ' ', text)
        # Rimuovi caratteri di controllo
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        return text.strip()

    def preprocess_text_with_alignment(self, raw_text: str) -> Tuple[str, List[int], Dict]:
        """
        Pulisce il testo rimuovendo parentesi, speaker marker e normalizzando spazi.
        Ritorna testo pulito, mappa di allineamento (index_clean -> index_raw), e statistiche.
        """
        local_stats = {
            'removed_parentheticals': 0,
            'removed_markers': 0,
            'fallback_count': 0
        }
        
        if not raw_text:
            return "", [], local_stats

        n = len(raw_text)
        keep = [True] * n
        
        # 1. Rimuovi parentesi (incluso nested)
        try:
             # Pattern ricorsivo per parentesi bilanciate
            pattern_parens = r'\((?>[^()]+|(?R))*\)'
            for m in regex_lib.finditer(pattern_parens, raw_text):
                local_stats['removed_parentheticals'] += 1
                for i in range(m.start(), m.end()):
                    keep[i] = False
        except Exception as e:
            print(f"Error in regex parentheses: {e}")

        # 2. Prepara passaggio intermedio per Speaker Marker
        # Ricostruiamo il testo parziale per applicare regex semantiche
        pass1_indices = [i for i, k in enumerate(keep) if k]
        pass1_text = "".join([raw_text[i] for i in pass1_indices])
        
        to_remove_pass1 = set()
        
        # Speaker marker: (?:^|[\.\!\?]\s)([A-ZÀ-Ú][A-ZÀ-Ú\s\'’]{2,})\.
        # Usa lookbehind per non rimuovere la punteggiatura precedente
        speaker_pattern = r'(?<=^|[\.\!\?]\s)([A-ZÀ-Ú][A-ZÀ-Ú\s\'’]{2,})\.'
        for m in regex_lib.finditer(speaker_pattern, pass1_text):
            local_stats['removed_markers'] += 1
            for i in range(m.start(), m.end()):
                to_remove_pass1.add(i)

        # Formule iniziali (es. "Signor Presidente...")
        # Pattern mirato a inizio stringa (o dopo spazi)
        init_pattern = r'^\s*(Signor\s+)?(Presidente|Vicepresidente)[^.]*[\.,]'
        m_init = regex_lib.match(init_pattern, pass1_text)
        if m_init:
             local_stats['removed_markers'] += 1
             for i in range(m_init.start(), m_init.end()):
                 to_remove_pass1.add(i)

        # 3. Normalizza spazi e costruisci mappa finale
        # Filtraggio pass1 -> pass2 (rimozione marker)
        pass2_indices = [idx for i, idx in enumerate(pass1_indices) if i not in to_remove_pass1]
        pass2_text = "".join([raw_text[i] for i in pass2_indices])
        
        # Normalizzazione spazi: \s+ -> ' '
        # Costruiamo il testo finale e la mappa
        final_chars = []
        final_map = []
        
        last_end = 0
        for m in re.finditer(r'\s+', pass2_text):
            # Aggiungi chunk precedente
            chunk_len = m.start() - last_end
            if chunk_len > 0:
                for j in range(chunk_len):
                    final_chars.append(pass2_text[last_end + j])
                    final_map.append(pass2_indices[last_end + j])
            
            # Aggiungi spazio singolo (mappato al primo spazio della sequenza)
            final_chars.append(' ')
            if m.end() > m.start():
                 final_map.append(pass2_indices[m.start()]) # Mappa all'inizio della sequenza spazi originali
            else:
                 final_map.append(pass2_indices[m.start()]) # Should not happen with \s+

            last_end = m.end()
            
        # Coda finale
        if last_end < len(pass2_text):
            chunk_len = len(pass2_text) - last_end
            for j in range(chunk_len):
                final_chars.append(pass2_text[last_end + j])
                final_map.append(pass2_indices[last_end + j])
        
        final_str = "".join(final_chars).strip()
        
        # Aggiusta mappa per lo strip (rimuovi indici scartati da strip)
        # Calcola quanti char tolti a sx e dx
        raw_final_str = "".join(final_chars)
        start_strip = len(raw_final_str) - len(raw_final_str.lstrip())
        end_strip = len(raw_final_str) - len(raw_final_str.rstrip())
        
        # Slice map
        if start_strip > 0:
            final_map = final_map[start_strip:]
        if end_strip > 0:
            final_map = final_map[:len(final_map)-end_strip] if end_strip < len(final_map) else []
            
        return final_str, final_map, local_stats

    def create_chunks(self, text: str, intervento_id: str, alignment_map: List[int]=None, raw_text: str=None) -> List[Dict]:
        """
        Divide il testo in chunk basati su frasi compiute.
        Supporta l'allineamento con il testo raw se fornito alignment_map.
        """
        if not text:
            return []

        # 1. Suddivisione in frasi
        sentence_endings = r'([.!?]\s+)'
        parts = re.split(sentence_endings, text)
        
        sentences = []
        current_sentence = ""
        
        for i in range(0, len(parts)-1, 2):
            text_part = parts[i]
            punct_part = parts[i+1]
            abbrev_pattern = r'\b(?:On|Sen|Prof|Dott|Avv|Sig|Sigg|lett|cfr|art|comma|n|pag|V|B)\.$'
            
            if re.search(abbrev_pattern, text_part + punct_part.strip()):
                current_sentence += text_part + punct_part
            else:
                sentences.append((current_sentence + text_part + punct_part).strip())
                current_sentence = ""
        
        if len(parts) % 2 != 0 and parts[-1]:
            sentences.append((current_sentence + parts[-1]).strip())
        elif current_sentence:
            sentences.append(current_sentence.strip())

        sentences = [s for s in sentences if s]
        if not sentences:
             return []

        # Mappa posizioni frasi nel testo preprocessed per risalire agli offset raw
        # Iteriamo sul testo cercando le frasi
        sentence_spans = []
        cursor = 0
        for s in sentences:
            # Trova la frase a partire dal cursore
            idx = text.find(s, cursor)
            if idx == -1:
                # Fallback: potrebbe non trovarla se ci sono differenze di spazi strane? 
                # Ma text viene da join? No, text è input.
                # Se 's' è stripped, e 'text' ha spazi normalizzati, dovrebbe matchare.
                # A meno che s non abbia spazi interni diversi. Ma text ha soli singolis spazi.
                continue
            sentence_spans.append({'start': idx, 'end': idx + len(s)})
            cursor = idx + len(s) # Avanza cursore

        # 2. Raggruppamento frasi
        chunks = []
        chunk_index = 0
        i = 0
        
        while i < len(sentences):
            current_chunk_sentences = []
            current_length = 0
            
            # Indici start/end del chunk relativi alle frasi
            start_sent_idx = i
            end_sent_idx = i

            j = i
            while j < len(sentences):
                sentence = sentences[j]
                if current_length + len(sentence) <= CHUNK_SIZE or not current_chunk_sentences:
                    current_chunk_sentences.append(sentence)
                    current_length += len(sentence)
                    end_sent_idx = j
                    j += 1
                else:
                    break
            
            chunk_text = " ".join(current_chunk_sentences)
            
            # Calcola offset RAW
            start_raw = -1
            end_raw = -1
            
            if alignment_map and start_sent_idx < len(sentence_spans) and end_sent_idx < len(sentence_spans):
                # Start del primo sentence
                s_start = sentence_spans[start_sent_idx]['start']
                # End dell'ultimo sentence
                s_end = sentence_spans[end_sent_idx]['end']
                
                if s_start < len(alignment_map) and (s_end - 1) < len(alignment_map):
                    start_raw = alignment_map[s_start]
                    # l'indice finale raw corrispondente all'ultimo carattere
                    end_raw = alignment_map[s_end - 1] + 1 
            
            chunks.append({
                'id': f"{intervento_id}_chunk_{chunk_index}",
                'testo': chunk_text,
                'indice': chunk_index,
                'char_count': len(chunk_text),
                'start_char_raw': start_raw,
                'end_char_raw': end_raw
            })
            chunk_index += 1
            
            if j == len(sentences):
                break
            
            # Overlap logic
            overlap_length = 0
            new_i = j
            while new_i > i + 1:
                prev_sentence = sentences[new_i - 1]
                if overlap_length + len(prev_sentence) <= CHUNK_OVERLAP:
                    overlap_length += len(prev_sentence)
                    new_i -= 1
                else:
                    if overlap_length == 0:
                        new_i -= 1
                    break
            
            i = new_i if new_i != j else j
                
        return chunks

    def parse_intervento(self, intervento_elem, seduta_id: str) -> Optional[Dict]:
        """
        Parsa un elemento intervento, unendo testoXHTML e interventoVirtuale.
        Ritorna None se è un intervento del PRESIDENTE o troppo corto.
        """
        intervento_id = intervento_elem.get('id')
        if not intervento_id:
            return None

        full_id = f"{seduta_id}_{intervento_id}"

        # Estrai testoXHTML
        testo_xhtml = intervento_elem.find('testoXHTML')

        # Verifica se è PRESIDENTE
        dep_id, cognome_nome, is_presidente = self.get_nominativo_info(testo_xhtml)

        if is_presidente:
            return None  # Salta interventi del presidente

        # Raccogli tutto il testo
        text_parts = []

        # Testo principale (escluso il nominativo iniziale)
        if testo_xhtml is not None:
            main_text = self.extract_text_from_element(testo_xhtml)
            # Rimuovi il nome dell'oratore dall'inizio se presente
            if cognome_nome and main_text.startswith(cognome_nome):
                main_text = main_text[len(cognome_nome):].lstrip('. ')
            text_parts.append(main_text)

        # Aggiungi tutti gli interventoVirtuale
        for iv in intervento_elem.findall('interventoVirtuale'):
            iv_text = self.extract_text_from_element(iv)
            if iv_text:
                text_parts.append(iv_text)

        # Unisci tutto il testo (Raw assembly)
        # Usa parsing di base senza pulizia aggressiva per il raw
        raw_text_parts = text_parts
        raw_text_full = " ".join(raw_text_parts)
        # Pulisci solo caratteri invisibili di base se necessario, ma mantieni raw
        # Usiamo clean_text solo per spazi base, ma ora la logica è spostata
        # Facciamo una versione "semi-raw" che ha spazi normalizzati ma contenuto integro? 
        # No, il raw deve essere integro.
        # Ma preprocess_text_with_alignment assume raw_text in input.
        
        # Preprocessing robusto
        clean_text, al_map, stats = self.preprocess_text_with_alignment(raw_text_full)
        
        # Filtra interventi troppo corti (sul clean text)
        if len(clean_text) < MIN_INTERVENTO_LENGTH:
            return None
            
        # Logging Audit (campionamento o full?)
        # Salviamo stats per audit finale
        self.stats['processed_interventi'] += 1
        if stats['removed_parentheticals'] > 0 or stats['removed_markers'] > 0:
            self.stats['with_removals'] += 1
            self.stats['total_parentheticals_removed'] += stats['removed_parentheticals']
            self.stats['total_markers_removed'] += stats['removed_markers']
            
            # Aggiungi a buffer audit
            self.audit_buffer.append({
                'intervento_id': full_id,
                'raw_preview': raw_text_full[:200],
                'preprocessed_preview': clean_text[:200],
                'removed_parentheticals': stats['removed_parentheticals'],
                'removed_markers': stats['removed_markers'],
                'fallback_count': stats['fallback_count'],
                'len_raw': len(raw_text_full),
                'len_clean': len(clean_text)
            })

        return {
            'id': full_id,
            'original_id': intervento_id,
            'testo_raw': raw_text_full,
            'testo_preprocessed': clean_text,
            'testo': clean_text, # Retrocompatibilità
            'alignment_map': al_map,
            'deputato_id': dep_id,
            'cognome_nome': cognome_nome,
            'char_count': len(clean_text)
        }

    def parse_votazione(self, votazione_elem, seduta_id: str, vot_index: int) -> Dict:
        """Parsa un elemento votazione."""
        def get_text(tag):
            elem = votazione_elem.find(tag)
            return elem.text.strip() if elem is not None and elem.text else None

        def get_int(tag):
            val = get_text(tag)
            try:
                return int(val) if val else None
            except:
                return None

        return {
            'id': f"{seduta_id}_vot_{vot_index}",
            'numero': get_int('numero'),
            'tipo': get_text('tipo'),
            'oggetto': get_text('oggetto'),
            'presenti': get_int('presenti'),
            'votanti': get_int('votanti'),
            'astenuti': get_int('astenuti'),
            'maggioranza': get_int('maggioranza'),
            'favorevoli': get_int('favorevoli'),
            'contrari': get_int('contrari'),
            'missione': get_int('missione'),
            'esito': get_text('esito')
        }


    def parse_xml_file(self, filepath: str) -> Dict:
        """Parsa un file XML stenografico completo."""
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Estrai info seduta
        seduta_id = f"leg{root.get('legislatura')}_sed{root.get('numero')}"
        seduta = {
            'id': seduta_id,
            'legislatura': int(root.get('legislatura')),
            'numero': int(root.get('numero')),
            'anno': int(root.get('anno')),
            'mese': int(root.get('mese')),
            'giorno': int(root.get('giorno')),
            'ramo': root.get('ramo'),
            'data': f"{root.get('giorno')}/{root.get('mese')}/{root.get('anno')}"
        }

        # Data estesa
        data_estesa = root.find('.//dataEstesa')
        if data_estesa is not None and data_estesa.text:
            seduta['dataEstesa'] = data_estesa.text.strip()

        # Raccogli tutti i dati
        dibattiti = []
        fasi = []
        interventi = []
        votazioni = []

        # Parsa il resoconto
        resoconto = root.find('resoconto')
        if resoconto is None:
            return {'seduta': seduta, 'dibattiti': [], 'fasi': [], 'interventi': [], 'votazioni': []}

        dibattito_order = 0

        # Interventi fuori dai dibattiti (es. apertura seduta)
        for int_elem in resoconto.findall('./intervento'):
            intervento = self.parse_intervento(int_elem, seduta_id)
            if intervento:
                intervento['parent_type'] = 'seduta'
                intervento['parent_id'] = seduta_id
                interventi.append(intervento)

        # Parsa dibattiti
        for dib_elem in resoconto.findall('dibattito'):
            dib_id = dib_elem.get('id')
            if not dib_id:
                continue

            full_dib_id = f"{seduta_id}_{dib_id}"
            titolo_elem = dib_elem.find('titolo')
            titolo = titolo_elem.text.strip() if titolo_elem is not None and titolo_elem.text else ""

            dibattiti.append({
                'id': full_dib_id,
                'original_id': dib_id,
                'titolo': titolo,
                'ordine': dibattito_order,
                'seduta_id': seduta_id
            })
            dibattito_order += 1

            # Interventi diretti nel dibattito
            intervento_order = 0
            for int_elem in dib_elem.findall('./intervento'):
                intervento = self.parse_intervento(int_elem, seduta_id)
                if intervento:
                    intervento['parent_type'] = 'dibattito'
                    intervento['parent_id'] = full_dib_id
                    intervento['ordine'] = intervento_order
                    interventi.append(intervento)
                    intervento_order += 1

            # Parsa fasi
            fase_order = 0
            for fase_elem in dib_elem.findall('fase'):
                fase_id = fase_elem.get('id')
                if not fase_id:
                    continue

                full_fase_id = f"{seduta_id}_{fase_id}"
                fase_titolo_elem = fase_elem.find('titolo')
                fase_titolo = fase_titolo_elem.text.strip() if fase_titolo_elem is not None and fase_titolo_elem.text else ""

                fasi.append({
                    'id': full_fase_id,
                    'original_id': fase_id,
                    'titolo': fase_titolo,
                    'ordine': fase_order,
                    'dibattito_id': full_dib_id
                })
                fase_order += 1

                # Interventi nella fase
                fase_int_order = 0
                for int_elem in fase_elem.findall('intervento'):
                    intervento = self.parse_intervento(int_elem, seduta_id)
                    if intervento:
                        intervento['parent_type'] = 'fase'
                        intervento['parent_id'] = full_fase_id
                        intervento['ordine'] = fase_int_order
                        interventi.append(intervento)
                        fase_int_order += 1

            # Parsa votazioni nel dibattito
            vot_index = 0
            for votazioni_elem in dib_elem.findall('.//votazioni'):
                for vot_elem in votazioni_elem.findall('votazione'):
                    votazione = self.parse_votazione(vot_elem, seduta_id, vot_index)
                    votazione['dibattito_id'] = full_dib_id
                    votazioni.append(votazione)
                    vot_index += 1
        
        # MERGE LOGIC: Unisci interventi spezzati (stesso oratore, continuazione con ellissi)
        # Nota: applichiamo il merge sulla lista completa 'interventi'.
        # Poiché 'interventi' è costruita iterando blocchi (top-level, then dibattiti -> fasi), 
        # l'ordine temporale è preservato SOLO se il documento XML segue questa gerarchia rigorosa.
        # Generalmente gli interventi spezzati sono adiacenti nello stesso blocco, quindi sono adiacenti nella lista.
        interventi = self.merge_continuation_interventions(interventi)
        
        return {
            'seduta': seduta,
            'dibattiti': dibattiti,
            'fasi': fasi,
            'interventi': interventi,
            'votazioni': votazioni
        }

