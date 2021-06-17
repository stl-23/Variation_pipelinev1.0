import os,sys
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath('./'))))
from vartools import getmyconfig,make_freec_config

samtools = getmyconfig.getConfig('Variation', 'samtools')
bcftools = getmyconfig.getConfig('Variation', 'bcftools')
vcfutils = getmyconfig.getConfig('Variation','vcfutils')
gatk4 = getmyconfig.getConfig('Variation', 'gatk4')
breakdancer = getmyconfig.getConfig('Variation', 'BreakDancer')
bam2cfg = getmyconfig.getConfig('Variation','bam2cfg')
crest = getmyconfig.getConfig('Variation','Crest')
extractSClip = getmyconfig.getConfig('Variation','extractSClip')
cnvnator = getmyconfig.getConfig('Variation', 'CNVnator')
cnvnator2VCF = getmyconfig.getConfig('Variation','cnvnator2VCF')
control_freec = getmyconfig.getConfig('Variation','control_freec')
freec_WGS_config = getmyconfig.getConfig('Variation','freec_WGS_config')
freec_WES_config = getmyconfig.getConfig('Variation','freec_WES_config')
splitSNPindelVCF = getmyconfig.getConfig('Variation','splitSNPindelVCF')

## known_site='--known-sites /path/to/ref1.vcf --known-sites /path/to/ref2.vcf ....'
def snp_indel_samtools(ref, input, sample, v_valling, bcftools_filter):
    outfile = ''
    #samtools_p = 'mpileup -C 50 -m 2 -F 0.002 -d 1000 -u -f'
    # vcfutils_p = 'varFilter -Q 20 -d 4 -D 1000'
    bcftools_mpileup = 'mpileup -d 1000 -Ov -f'
    bcftools_call = 'call -mv -Oz -o'
    ### Hard filtering
    if v_valling == 'single':  ## input is a single bam file
        outfile = """{bcftools} {bcftools_mpileup} {ref} {input_bam} | {bcftools} {bcftools_call} {sample}.all.vcf.gz
{bcftools} filter {bcftools_filter} {sample}.all.vcf.gz -o {sample}.filter.vcf.gz
python {splitSNPindelVCF} {sample}.filter.vcf.gz {sample}.samtools
{bcftools} view {sample}.samtools.snp.vcf -Oz -o {sample}.samtools.snp.vcf.gz
{bcftools} view {sample}.samtools.indel.vcf -Oz -o {sample}.samtools.indel.vcf.gz
{gatk4} IndexFeatureFile -I {sample}.samtools.snp.vcf.gz 
{gatk4} IndexFeatureFile -I {sample}.samtools.indel.vcf.gz
rm {sample}.samtools.snp.vcf {sample}.samtools.indel.vcf 
        """.format(bcftools=bcftools,bcftools_mpileup=bcftools_mpileup,bcftools_call=bcftools_call,
                   ref=ref,sample=sample,input_bam=input, gatk4=gatk4,
                   bcftools_filter=bcftools_filter,splitSNPindelVCF=splitSNPindelVCF)
    elif v_valling == 'join': ## input is a list of bam files
        input_bams = ' '.join(input)
        outfile = """{bcftools} {bcftools_mpileup} {ref} {input_bams} | {bcftools} {bcftools_call} {sample}.all.vcf.gz
{bcftools} filter {bcftools_filter} {sample}.all.vcf.gz -o {sample}.filter.vcf.gz
python {splitSNPindelVCF} {sample}.filter.vcf.gz {sample}.samtools
{bcftools} view {sample}.samtools.snp.vcf -Oz -o {sample}.samtools.snp.vcf.gz
{bcftools} view {sample}.samtools.indel.vcf -Oz -o {sample}.samtools.indel.vcf.gz
{gatk4} IndexFeatureFile -I {sample}.samtools.snp.vcf.gz 
{gatk4} IndexFeatureFile -I {sample}.samtools.indel.vcf.gz
rm {sample}.samtools.snp.vcf {sample}.samtools.indel.vcf """.format(
            bcftools=bcftools, bcftools_mpileup=bcftools_mpileup, bcftools_call=bcftools_call,
            ref=ref, sample=sample, input_bams=input_bams,gatk4=gatk4,
            bcftools_filter=bcftools_filter, splitSNPindelVCF=splitSNPindelVCF
        )
    return outfile

def snp_indel_gatk(ref, input, sample, gvcf, bqsr_dir):
    outfile = ''
    if bqsr_dir:  #### BQSR (Recalibration Base Quality Score)
        lst = os.listdir(os.path.abspath(bqsr_dir))
        known_site = ' '.join(["--known-sites "+bqsr_dir+"/"+vcf for vcf in lst if vcf.endswith('.vcf.gz')])
        if gvcf == "T":
            outfile = """{gatk4} BaseRecalibrator -R {ref} -I {input} {known_site} -O {sample}.recal.table
{gatk4} ApplyBQSR --bqsr-recal-file {sample}.recal.table -R {ref} -I {input} -O {sample}.BQSR.bam
{gatk4} HaplotypeCaller -R {ref} -I {sample}.BQSR.bam -ERC GVCF -O {sample}.g.vcf
                    """.format(gatk4=gatk4, ref=ref, input=input, sample=sample, known_site=known_site)

        elif gvcf == "F":
            outfile = """{gatk4} BaseRecalibrator -R {ref} -I {input} {known_site} -O {sample}.recal.table
{gatk4} ApplyBQSR --bqsr-recal-file {sample}.recal.table -R {ref} -I {input} -O {sample}.BQSR.bam
{gatk4} HaplotypeCaller -R {ref} -I {sample}.BQSR.bam -O {sample}.vcf
                        """.format(gatk4=gatk4, ref=ref, input=input, sample=sample, known_site=known_site)
    elif not bqsr_dir:
        if gvcf == "T":
            outfile = """{gatk4} HaplotypeCaller -R {ref} -I {input} -ERC GVCF -O {sample}.g.vcf""".format(gatk4=gatk4, ref=ref, input=input, sample=sample)
        elif gvcf == "F":
            outfile = """{gatk4} HaplotypeCaller -R {ref} -I {input} -O {sample}.vcf""".format(gatk4=gatk4, ref=ref, input=input, sample=sample)
    return outfile

def samtool_gatk_combine(sample):  ## Samtools and GATK pipelines
    cmd = """{gatk4} SelectVariants --variant {sample}.snps.gatk.vcf.gz --concordance {sample}.samtools.snp.vcf.gz -O {sample}.final.concordance.snp.gz
{gatk4} SelectVariants --variant {sample}.indel.gatk.vcf.gz --concordance {sample}.samtools.indel.vcf.gz -O {sample}.final.concordance.indel.gz""".format(
        gatk4=gatk4,sample=sample)
    return cmd

def ngs_sv(sample1,sample2,ref,tool='breakdancer',rm_germline="false"): ## sample1:disease/somatic; sample2:control
    outfile = ''
    breakdancer_p = '-q 20 -d'
    #crest_p = ''
    if tool == 'breakdancer':  ## Only use paired end reads
        if rm_germline == "true": ## somatic SV
            pass
        elif rm_germline == "false": ## germline/common SV
            outfile = """perl {bam2cfg} q 20 -c 4 -g -h {sample1} {sample1}.cfg
{breakdancer} {breakdancer_p} {sample1} {sample1}.cfg > {sample1}.raw.ctx""".format(
            bam2cfg=bam2cfg,sample1=sample1,breakdancer=breakdancer,breakdancer_p=breakdancer_p
        )
    elif tool == 'crest':      ## Can use both paired end and singe end reads
        if rm_germline == "true":  ## somatic SV
            outfile = """perl {extractSClip} -i {sample1}.rmdup.bam --ref_genome {ref} -p {sample1}
perl {crest} -f {sample1}.cover -d {sample1}.rmdup.bam -g {sample2}.rmdup.bam --ref_genome {ref} -t {ref}.2bit -p {sample1}
            """.format(
                extractSClip=extractSClip,sample1=sample1,sample2=sample2,
                crest=crest,ref=ref
            )
        elif rm_germline == "false": ## germline/common SV
            outfile = """perl {extractSClip} -i {sample1} --ref_genome {ref} -p {sample1}
perl {crest} -f {sample1}.cover -d {sample1} --ref_genome {ref} -t {ref}.2bit -p {sample1}""".format(
                extractSClip=extractSClip, sample1=sample1,crest=crest,ref=ref
            )
    return outfile
def ngs_cnv(sample1, sample2, ref, outdir, tool='control-freec',species='human',stragety="WGS",rm_germline="false"):
    outfile = ''
    if tool == 'cnvnator':
        bin_size = '1000'
        ref_dir = os.path.dirname(ref)
        outfile = """{cnvnator} -root {sample1}.root -tree {sample1} 
{cnvnator} -root {sample1}.root -his {bin_size} -d {ref_dir}
{cnvnator} -root {sample1}.root -stat {bin_size}
{cnvnator} -root {sample1}.root -partition {bin_size}
{cnvnator} -root {sample1}.root -call {bin_size} > {sample1}.cnv.call.txt
perl {cnvnator2VCF} {sample1}.cnv.call.txt > {sample1}.cnv.vcf
        """.format(cnvnator=cnvnator,sample1=sample1,ref_dir=ref_dir,cnvnator2VCF=cnvnator2VCF,bin_size=bin_size)
    elif tool == 'control-freec':
        if species == 'human':
            if stragety == "WGS":
                if rm_germline == "true":
                    sample_data = sample1+'.rmdup.bam'
                    control_data = sample2+'.rmdup.bam'
                    config_wgs_add_control=make_freec_config.modify(sample_data,control_data,ref,outdir,'human','WGS','Y')
                    outfile = """{control_freec} -conf ./config.list
                    """.format(control_freec=control_freec)
                    return config_wgs_add_control, outfile
                elif rm_germline == "false":
                    pre = sample1.rstrip('/').split('/')[-1]
                    config_wgs_no_control=make_freec_config.modify(sample1,'',ref,outdir,'human','WGS','N')
                    outfile = """{control_freec} -conf {pre}_config_wgs_no_control.list
                    """.format(control_freec=control_freec,pre=pre)
                    return config_wgs_no_control, outfile
            elif stragety == "WES":
                if rm_germline == "true":
                    sample_data = sample1 + '.rmdup.bam'
                    control_data = sample2 + '.rmdup.bam'
                    config_wes_add_control = make_freec_config.modify(sample_data,control_data,ref,outdir,'human','WES','Y')
                    outfile = """{control_freec} -conf ./config.list
                    """.format(control_freec=control_freec)
                    return config_wes_add_control, outfile
                elif rm_germline == "false":
                    pre = sample1.rstrip('/').split('/')[-1]
                    config_wes_no_control = make_freec_config.modify(sample1, '', ref,outdir,'human', 'WES', 'N')
                    outfile = """{control_freec} -conf {pre}_config_wgs_no_control.list
                    """.format(control_freec=control_freec,pre=pre)
                    return config_wes_no_control, outfile
        elif species == 'non-human':
            pass

    elif tool == 'ExomeCNV': ## WES
        pass