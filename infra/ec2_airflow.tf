resource "aws_security_group" "airflow_sg" {
  name   = "${var.project}-${var.env}-airflow-sg"
  vpc_id = aws_vpc.main.id
  ingress { 
    from_port = 22   
    to_port = 22   
    protocol = "tcp" 
    cidr_blocks = [var.allowed_cidr] 
    }
  ingress { 
    from_port = 8080 
    to_port = 8080 
    protocol = "tcp" 
    cidr_blocks = [var.allowed_cidr] 
    }
  egress  { 
    from_port = 0    
    to_port = 0    
    protocol = "-1"  
    cidr_blocks = ["0.0.0.0/0"] 
    }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners = ["099720109477"] # Canonical
  filter { 
    name = "name" 
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"] 
    }
}

resource "aws_iam_role" "airflow_ec2_role" {
  name = "${var.project}-${var.env}-airflow-ec2-role"
  assume_role_policy = jsonencode(
    {
        Version="2012-10-17", 
        Statement=[
            {
                Effect="Allow",
                Principal={
                    Service="ec2.amazonaws.com"
                    },
                Action="sts:AssumeRole"
            }
        ]
  })
}

# Inline policy: S3 rw (buckets), Lambda invoke, CloudWatch logs optional
resource "aws_iam_role_policy" "airflow_ec2_policy" {
  name = "${var.project}-${var.env}-airflow-ec2-policy"
  role = aws_iam_role.airflow_ec2_role.id
  policy = jsonencode({
    Version="2012-10-17",
    Statement=[
      {Effect="Allow", Action=["s3:*"], Resource=[
        "arn:aws:s3:::${var.raw_bucket}", "arn:aws:s3:::${var.raw_bucket}/*",
        "arn:aws:s3:::${var.staged_bucket}", "arn:aws:s3:::${var.staged_bucket}/*",
        "arn:aws:s3:::${var.logs_bucket}", "arn:aws:s3:::${var.logs_bucket}/*"
      ]},
      {Effect="Allow", Action=["lambda:InvokeFunction"], Resource="*"}
    ]
  })
}

resource "aws_iam_instance_profile" "airflow" {
  name = "${var.project}-${var.env}-airflow-profile"
  role = aws_iam_role.airflow_ec2_role.name
}

resource "aws_instance" "airflow" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t2.micro"
  key_name               = var.ec2_key_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.airflow_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.airflow.name
  user_data = base64encode(file("${path.module}/user_data/airflow_docker.sh"))
  tags = { Name = "${var.project}-${var.env}-airflow" }
}