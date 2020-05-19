###############################################################################
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    (at your option) any later version.                                      #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program. If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

import os
import sys
import argparse
import logging
from collections import defaultdict

from biolib.taxonomy import Taxonomy

from gtdb_species_clusters.genomes import Genomes
from gtdb_species_clusters.species_priority_manager import SpeciesPriorityManager

from gtdb_species_clusters.taxon_utils import (specific_epithet,
                                                longest_common_prefix)


class PMC_CheckTypeStrains(object):
    """Check for agreement between GTDB species and genomes assembled from type strain of species."""

    def __init__(self, output_dir):
        """Initialization."""
        
        self.output_dir = output_dir
        self.logger = logging.getLogger('timestamp')
        
    def _test_same_epithet(self, epithet1, epithet2):
        """Test if species epithet are the same, except for changes due to difference in the gender of the genus."""
        
        if epithet1 == epithet2:
            return True
            
        lcp = longest_common_prefix(epithet1, epithet2)
        if len(lcp) >= min(len(epithet1), len(epithet2)) - 3:
            # a small change to the suffix presumably reflecting
            # a change in the gender of the genus
            return True
            
        return False

    def run(self,
                manual_taxonomy,
                cur_gtdb_metadata_file,
                uba_genome_paths,
                qc_passed_file,
                ncbi_genbank_assembly_file,
                untrustworthy_type_file,
                synonym_file,
                gtdb_type_strains_ledger,
                sp_priority_ledger,
                dsmz_bacnames_file):
        """Finalize species names based on results of manual curation."""
        
        # initialize species priority manager
        sp_priority_mngr = SpeciesPriorityManager(sp_priority_ledger,
                                                    dsmz_bacnames_file)

        # identify species and genus names updated during manual curation
        self.logger.info('Parsing manually curated taxonomy.')
        mc_taxonomy = Taxonomy().read(manual_taxonomy, use_canonical_gid=True)
        self.logger.info(' - read taxonomy for {:,} genomes.'.format(len(mc_taxonomy)))

        # create current GTDB genome sets
        self.logger.info('Creating current GTDB genome set.')
        cur_genomes = Genomes()
        cur_genomes.load_from_metadata_file(cur_gtdb_metadata_file,
                                                gtdb_type_strains_ledger=gtdb_type_strains_ledger,
                                                create_sp_clusters=False,
                                                uba_genome_file=uba_genome_paths,
                                                qc_passed_file=qc_passed_file,
                                                ncbi_genbank_assembly_file=ncbi_genbank_assembly_file,
                                                untrustworthy_type_ledger=untrustworthy_type_file)
        self.logger.info(f' ... current genome set contains {len(cur_genomes):,} genomes.')
        
        # *** CHECK
        print('G003992675', cur_genomes['G003992675'].is_gtdb_type_strain())
        print('G003149745', cur_genomes['G003149745'].is_gtdb_type_strain())

        # establish appropriate species names for GTDB clusters with new representatives
        self.logger.info('Identifying type strain genomes with incongruent GTDB species assignments.')
        fout = open(os.path.join(self.output_dir, 'type_strains_incongruencies.tsv'), 'w')
        fout.write('Genome ID\tGTDB species\tNCBI species\tNCBI RefSeq note\n')
        num_incongruent = 0
        for rid, taxa in mc_taxonomy.items():
            if cur_genomes[rid].is_gtdb_type_strain():
                gtdb_sp = taxa[Taxonomy.SPECIES_INDEX]
                ncbi_sp = cur_genomes[rid].ncbi_taxa.species
                if ncbi_sp == 's__':
                    # NCBI taxonomy is sometimes behind the genome annotation pages,
                    # and do not have a species assignment even for type strain genome
                    continue 
                
                if not self._test_same_epithet(specific_epithet(gtdb_sp), specific_epithet(ncbi_sp)):
                    num_incongruent += 1
                    fout.write('{}\t{}\t{}\t{}\n'.format(
                                rid,
                                gtdb_sp,
                                ncbi_sp,
                                cur_genomes[rid].excluded_from_refseq_note))
      
        self.logger.info(' - identified {:,} genomes with incongruent species assignments.'.format(num_incongruent))
        fout.close()
    