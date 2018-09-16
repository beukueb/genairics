#-*- coding: utf-8 -*-
"""genairics project variants analysis module 
tasks to build phylogenetic trees, etc.
"""
from genairics import pb
from genairics.tasks import ProjectTask
import os

class VariantTree(ProjectTask):
    variantTreeThreshold = pb.FloatParameter(10,description='Quality threshold, variants called with lower value are discarded')
    
    def output(self):
        return pb.LocalTarget(os.path.join(self.projectresults,'samples_phylo_tree.svg'))

    def run(self):
        from scipy.cluster.hierarchy import dendrogram, linkage, cophenet
        from scipy.spatial.distance import pdist
        import matplotlib.pyplot as plt

        # Make dataframe
        variantfiles = self.getSampleResultFiles('variants.vcf')
        columns = [
            'CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL',
            'FILTER', 'INFO', 'FORMAT', 'alignment.sorted.bam'
        ]
        variations = [
            pd.read_table(
                v,comment='#',names=columns
            )[['CHROM','POS','QUAL']].rename(
                {'QUAL':os.path.basename(os.path.dirname(v))},axis=1
            ).groupby(['CHROM','POS']).mean()
            for v in variantfiles
        ]
        variations = pd.concat(variations, join='outer', axis=1)
        variations_binary = variations.fillna(0) > self.variantTreeThreshold
        variations_binary = variations_binary.T # rows=samples, cols=features

        # Build tree
        Z = linkage(variations_binary, 'ward')
        c, coph_dists = cophenet(Z, pdist(variations_binary))
        self.print('Linkage correlation',c)

        fig, ax = plt.subplots(figsize=(25, 10))
        ax.set_title('Hierarchical Clustering Dendrogram')
        ax.set_xlabel('Sample')
        ax.set_ylabel('Distance')
        dendrogram(
            Z,
            leaf_rotation=90.,  # rotates the x axis labels
            leaf_font_size=8.,  # font size for the x axis labels
            labels = variations_binary.index,
            ax = ax
        )
        fig.savefig(self.output().path)


